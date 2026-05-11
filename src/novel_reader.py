
def read_novel(file_path: str) -> str:
    """
    读取小说文件，支持多种编码方式

    Args:
        file_path: 小说文件路径

    Returns:
        小说文本内容

    Raises:
        FileNotFoundError: 文件不存在时抛出
        IOError: 文件读取失败时抛出
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            raise
    
    raise IOError(f"无法读取文件: {file_path}，尝试了以下编码方式: {', '.join(encodings)}")

