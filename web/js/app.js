// ==================== 状态管理 ====================
let uploadedFile = null;
let uploadedFileName = '';
let isGenerating = false;
let eventSource = null;
let receivedText = '';
let traceCount = 0;

// ==================== Toast 提示 ====================
function showToast(msg, duration) {
  if (duration === undefined) duration = 2000;
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(function() { t.classList.remove('show'); }, duration);
}

// ==================== 文件拖拽 ====================
var dropZone = document.getElementById('dropZone');
var fileInput = document.getElementById('fileInput');

dropZone.addEventListener('click', function() { fileInput.click(); });

dropZone.addEventListener('dragover', function(e) {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', function() {
  dropZone.classList.remove('drag-over');
});
dropZone.addEventListener('drop', function(e) {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  var file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.txt')) handleFile(file);
  else showToast('请上传 .txt 文件');
});
fileInput.addEventListener('change', function(e) {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

function handleFile(file) {
  uploadedFile = file;
  uploadedFileName = file.name;
  dropZone.classList.add('has-file');
  dropZone.querySelector('.dz-content').innerHTML =
    '<div class="dz-icon">✓</div>' +
    '<div class="dz-text">' + file.name + '</div>' +
    '<div class="dz-hint">' + (file.size / 1024).toFixed(1) + ' KB · 已加载</div>';
  document.getElementById('btnStart').disabled = false;
  showToast('文件已加载: ' + file.name);
}

// ==================== 开始生成 (SSE 流式) ====================
function startGeneration() {
  if (isGenerating || !uploadedFile) return;
  isGenerating = true;

  var btnStart = document.getElementById('btnStart');
  var btnStop = document.getElementById('btnStop');
  var btnExport = document.getElementById('btnExport');
  var editor = document.getElementById('editor');
  var status = document.getElementById('progressStatus');
  var percent = document.getElementById('progressPercent');
  var fill = document.getElementById('progressFill');

  btnStart.disabled = true;
  btnStop.disabled = false;
  btnExport.disabled = true;
  editor.textContent = '';
  editor.classList.add('streaming-cursor');
  receivedText = '';
  traceCount = 0;
  document.getElementById('llmTraceList').innerHTML = '';
  document.getElementById('tokenPrompt').textContent = '0';
  document.getElementById('tokenCompletion').textContent = '0';
  document.getElementById('tokenTotal').textContent = '0';

  status.textContent = '正在上传文件...';
  fill.style.width = '0%';
  percent.textContent = '0%';

  // 先将文件上传到后端
  var formData = new FormData();
  formData.append('file', uploadedFile);

  fetch('/upload', { method: 'POST', body: formData })
    .then(function(res) {
      if (!res.ok) throw new Error('上传失败');
      return res.json();
    })
    .then(function(data) {
      status.textContent = '正在生成剧本...';

      // 建立 SSE 连接，传递集数配置参数
      var minEp = document.getElementById('minEpisodes').value;
      var maxEp = document.getElementById('maxEpisodes').value;
      eventSource = new EventSource('/generate/' + data.file_id + '?min_episodes=' + minEp + '&max_episodes=' + maxEp);

      eventSource.onmessage = function(e) {
        var msg = JSON.parse(e.data);

        if (msg.type === 'llm_trace') {
          renderTrace(msg);
        } else if (msg.type === 'tokens') {
          document.getElementById('tokenPrompt').textContent = msg.prompt_tokens.toLocaleString();
          document.getElementById('tokenCompletion').textContent = msg.completion_tokens.toLocaleString();
          document.getElementById('tokenTotal').textContent = msg.total_tokens.toLocaleString();
        } else if (msg.type === 'stream') {
          // 流式输出：逐 token 追加到编辑器
          receivedText += msg.text;
          editor.textContent = receivedText;
          editor.scrollTop = editor.scrollHeight;
        } else if (msg.type === 'chunk') {
          receivedText += msg.text;
          editor.textContent = receivedText;
          var p = Math.min(100, Math.floor(msg.progress));
          fill.style.width = p + '%';
          percent.textContent = p + '%';
          status.textContent = '正在生成... ' + p + '%';
          editor.scrollTop = editor.scrollHeight;
        } else if (msg.type === 'done') {
          closeSSE();
          isGenerating = false;
          btnStart.disabled = false;
          btnStop.disabled = true;
          btnExport.disabled = false;
          editor.classList.remove('streaming-cursor');
          status.textContent = '生成完成！';
          fill.style.width = '100%';
          percent.textContent = '100%';
          showToast('剧本生成完成！可以编辑后导出。');
        } else if (msg.type === 'error') {
          closeSSE();
          isGenerating = false;
          btnStart.disabled = false;
          btnStop.disabled = true;
          editor.classList.remove('streaming-cursor');
          status.textContent = '生成失败: ' + msg.error;
          showToast('生成失败: ' + msg.error, 4000);
        }
      };

      eventSource.onerror = function() {
        closeSSE();
        isGenerating = false;
        btnStart.disabled = false;
        btnStop.disabled = true;
        editor.classList.remove('streaming-cursor');
        status.textContent = '连接中断';
        showToast('SSE 连接中断', 4000);
      };
    })
    .catch(function(err) {
      isGenerating = false;
      btnStart.disabled = false;
      btnStop.disabled = true;
      editor.classList.remove('streaming-cursor');
      status.textContent = '上传失败';
      showToast('上传失败: ' + err.message, 4000);
    });
}

// ==================== LLM 调用详情渲染 ====================
function renderTrace(msg) {
  traceCount++;
  var list = document.getElementById('llmTraceList');
  var id = 'trace-' + traceCount;

  var item = document.createElement('div');
  item.className = 'trace-item';
  item.id = id;

  item.innerHTML =
    '<div class="trace-header" onclick="toggleTrace(\'' + id + '\')">' +
      '<span>' + escapeHtml(msg.stage) + '</span>' +
      '<span class="trace-arrow">&#9654;</span>' +
    '</div>' +
    '<div class="trace-body">' +
      '<div class="trace-section">' +
        '<div class="trace-label">System Prompt</div>' +
        '<div class="trace-content">' + escapeHtml(msg.system_prompt) + '</div>' +
      '</div>' +
      '<div class="trace-section">' +
        '<div class="trace-label">User Prompt</div>' +
        '<div class="trace-content">' + escapeHtml(msg.user_prompt) + '</div>' +
      '</div>' +
      '<div class="trace-section">' +
        '<div class="trace-label">LLM Response</div>' +
        '<div class="trace-content">' + escapeHtml(msg.response) + '</div>' +
      '</div>' +
    '</div>';

  list.appendChild(item);
  // 自动展开最新一个
  if (traceCount > 1) {
    var prev = document.getElementById('trace-' + (traceCount - 1));
    if (prev) prev.classList.remove('open');
  }
  item.classList.add('open');
}

function toggleTrace(id) {
  var item = document.getElementById(id);
  if (item) item.classList.toggle('open');
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

function closeSSE() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

// ==================== 停止生成 ====================
function stopGeneration() {
  if (!isGenerating) return;
  closeSSE();
  isGenerating = false;

  // 通知后端停止
  fetch('/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  }).catch(function() {});

  document.getElementById('btnStart').disabled = false;
  document.getElementById('btnStop').disabled = true;
  document.getElementById('editor').classList.remove('streaming-cursor');
  document.getElementById('progressStatus').textContent = '已停止';
  showToast('生成已停止');
}

// ==================== 导出 ====================
function exportScript() {
  var editor = document.getElementById('editor');
  var content = editor.textContent || editor.innerText;
  if (!content || content === '等待生成剧本...') {
    showToast('没有可导出的内容');
    return;
  }
  var blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = uploadedFileName.replace('.txt', '') + '_剧本.txt';
  a.click();
  URL.revokeObjectURL(url);
  showToast('剧本已导出！');
}

// ==================== 清空编辑器 ====================
function clearEditor() {
  document.getElementById('editor').textContent = '';
  receivedText = '';
}
