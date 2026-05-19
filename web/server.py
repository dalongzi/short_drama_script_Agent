"""
短剧剧本改编 Agent - Flask 后端服务
提供文件上传、SSE 流式剧本生成、停止生成等 API。
"""

import os
import sys
import json
import uuid
import re
import threading

from flask import Flask, request, jsonify, Response, send_from_directory

# 将项目根目录加入 sys.path 以导入 src 模块
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.config import Config
from src.llm_client import LLMClient
from src.script_writer import ScriptWriter, BatchRange, AutoPromptContext

app = Flask(__name__, static_folder='.', static_url_path='')

# 存储上传的文件内容 {file_id: novel_text}
uploaded_files = {}

# 生成状态 {file_id: {'running': bool, 'result': str, 'error': str, 'progress': float}}
generation_state = {}


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """接收上传的小说 .txt 文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if not file.filename or not file.filename.endswith('.txt'):
        return jsonify({'error': '请上传 .txt 文件'}), 400

    raw = file.read()
    text = None
    for enc in ['utf-8', 'gbk', 'gb2312', 'cp1252']:
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        return jsonify({'error': '无法解析文件编码'}), 400

    file_id = str(uuid.uuid4())
    uploaded_files[file_id] = text
    generation_state[file_id] = {'running': False, 'result': '', 'error': '', 'progress': 0.0}

    return jsonify({'file_id': file_id, 'filename': file.filename, 'length': len(text)})


def _sse(event):
    """将事件格式化为 SSE 格式"""
    return f'data: {json.dumps(event, ensure_ascii=False)}\n\n'


def _emit_llm_trace(yield_fn, stage: str, system_prompt: str, user_prompt: str, response: str):
    """发送 LLM 调用追踪事件"""
    yield_fn(_sse({
        'type': 'llm_trace',
        'stage': stage,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'response': response,
    }))


@app.route('/generate/<file_id>', methods=['GET'])
def generate_script(file_id):
    """SSE 流式输出剧本生成过程"""
    if file_id not in uploaded_files:
        return jsonify({'error': '文件不存在'}), 404

    def event_stream():
        novel_text = uploaded_files[file_id]
        state = generation_state[file_id]
        state['running'] = True
        state['result'] = ''
        state['error'] = ''
        state['progress'] = 0.0

        total_tokens = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

        try:
            config = Config()
            llm_client = LLMClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.model
            )
            script_writer = ScriptWriter(
                llm_client,
                template_path=os.path.join(ROOT_DIR, 'data', '短剧剧本写作格式模板.md')
            )

            def _emit_tokens():
                """发送当前累计 token 消耗"""
                yield _sse({
                    'type': 'tokens',
                    'prompt_tokens': total_tokens['prompt_tokens'],
                    'completion_tokens': total_tokens['completion_tokens'],
                    'total_tokens': total_tokens['total_tokens'],
                })

            # ===== 阶段一：决定集数 =====
            yield _sse({'type': 'chunk', 'text': '', 'progress': 2, 'status': '正在分析小说内容，决定集数...'})

            template_content = script_writer._read_template()
            sys_d, usr_d = script_writer._build_decide_episodes_prompt(novel_text, 60, 100)
            decide_resp, usage_d = llm_client.generate(sys_d, usr_d)
            total_tokens['prompt_tokens'] += usage_d['prompt_tokens']
            total_tokens['completion_tokens'] += usage_d['completion_tokens']
            total_tokens['total_tokens'] += usage_d['total_tokens']
            yield from _emit_tokens()

            yield _sse({
                'type': 'llm_trace',
                'stage': '阶段一：决定集数',
                'system_prompt': sys_d,
                'user_prompt': usr_d,
                'response': decide_resp,
            })

            # 解析集数
            _EPISODE_COUNT_PATTERN = re.compile(r'集数[：:]\s*(\d+)')
            match = _EPISODE_COUNT_PATTERN.search(decide_resp)
            total_episodes = int(match.group(1)) if match else 80

            yield _sse({
                'type': 'chunk',
                'text': f'【分析完成】LLM 决策的总集数: {total_episodes} 集\n\n',
                'progress': 5,
                'status': f'确定集数为 {total_episodes} 集，正在生成大纲...'
            })

            # ===== 阶段二：生成逐集大纲 =====
            sys_o, usr_o = script_writer._build_outline_prompt(novel_text, total_episodes)
            outline_response, usage_o = llm_client.generate(sys_o, usr_o)
            total_tokens['prompt_tokens'] += usage_o['prompt_tokens']
            total_tokens['completion_tokens'] += usage_o['completion_tokens']
            total_tokens['total_tokens'] += usage_o['total_tokens']
            yield from _emit_tokens()

            yield _sse({
                'type': 'llm_trace',
                'stage': '阶段二：生成逐集大纲',
                'system_prompt': sys_o,
                'user_prompt': usr_o,
                'response': outline_response,
            })

            yield _sse({
                'type': 'chunk',
                'text': '【大纲生成完成】\n\n',
                'progress': 10,
                'status': '大纲已生成，正在分批生成剧本正文...'
            })

            # ===== 阶段三：按大纲分批生成正文 =====
            outline_dict = script_writer._parse_outline(outline_response)
            chapters = script_writer._split_novel_by_chapters(novel_text)
            novel_segments = script_writer._map_episodes_to_segments(chapters, total_episodes)

            ctx = AutoPromptContext(
                template_content=template_content,
                total_episodes=total_episodes,
                outline_dict=outline_dict,
                novel_segments=novel_segments,
            )

            batch_size = 10
            current_episode = 1
            all_parts = []

            while current_episode <= total_episodes:
                if not state['running']:
                    yield _sse({'type': 'chunk', 'text': '\n\n【已停止】', 'progress': 100, 'status': '已停止'})
                    state['running'] = False
                    return

                end_episode = min(current_episode + batch_size - 1, total_episodes)

                yield _sse({
                    'type': 'chunk',
                    'text': '',
                    'progress': 10 + int((current_episode / total_episodes) * 5),
                    'status': f'正在生成第 {current_episode} - {end_episode} 集...'
                })

                batch = BatchRange(start=current_episode, end=end_episode)
                batch_outline = script_writer._get_outline_range(outline_dict, current_episode, end_episode)
                batch_segment = '\n\n'.join(
                    novel_segments[ep] for ep in range(current_episode, end_episode + 1) if ep in novel_segments
                )

                sys_p, usr_p = script_writer._build_auto_prompt(batch, batch_outline, batch_segment, ctx)

                # 流式生成：逐 token 推送给前端
                batch_content_parts = []
                for kind, data in llm_client.generate_stream(sys_p, usr_p):
                    if kind == 'token':
                        batch_content_parts.append(data)
                        yield _sse({
                            'type': 'stream',
                            'text': data,
                        })
                    elif kind == 'usage':
                        total_tokens['prompt_tokens'] += data['prompt_tokens']
                        total_tokens['completion_tokens'] += data['completion_tokens']
                        total_tokens['total_tokens'] += data['total_tokens']
                        yield from _emit_tokens()

                batch_content = ''.join(batch_content_parts)

                # 发送完整的 LLM 调用追踪信息
                yield _sse({
                    'type': 'llm_trace',
                    'stage': f'阶段三：生成第 {current_episode}-{end_episode} 集',
                    'system_prompt': sys_p,
                    'user_prompt': usr_p,
                    'response': batch_content,
                })

                # 校验格式
                from src.format_validator import validate_script_format
                is_valid, issues = validate_script_format(batch_content, os.path.join(ROOT_DIR, 'data', '短剧剧本写作格式模板.md'))
                if not is_valid:
                    batch_content += '\n\n【格式校验问题】\n' + '\n'.join(issues)

                progress = 10 + int((end_episode / total_episodes) * 88)
                yield _sse({
                    'type': 'chunk',
                    'text': f'\n\n【第 {current_episode}-{end_episode} 集生成完成】\n\n',
                    'progress': progress,
                    'status': f'第 {current_episode}-{end_episode} 集完成，进度 {progress}%'
                })

                all_parts.append(batch_content)
                state['progress'] = progress
                current_episode = end_episode + 1

            # 完成
            full_result = '\n\n'.join(all_parts)
            full_result = f'【集数：{total_episodes}集】\n\n' + full_result
            state['result'] = full_result
            state['running'] = False
            yield _sse({'type': 'done', 'text': '', 'progress': 100, 'status': '生成完成！'})

        except Exception as e:
            state['running'] = False
            state['error'] = str(e)
            yield _sse({'type': 'error', 'error': str(e)})

    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    })


@app.route('/stop', methods=['POST'])
def stop_generation():
    """停止当前生成任务"""
    for fid in generation_state:
        if generation_state[fid].get('running'):
            generation_state[fid]['running'] = False
    return jsonify({'status': 'stopped'})


if __name__ == '__main__':
    print('=== 短剧剧本改编 Agent 后端服务 ===')
    print('访问地址: http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
