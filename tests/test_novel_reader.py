
import os
import pytest
from src.novel_reader import read_novel


def test_read_novel_success(tmp_path):
    test_file = tmp_path / "test_novel.txt"
    test_content = "这是小说内容"
    test_file.write_text(test_content, encoding="utf-8")

    content = read_novel(str(test_file))
    assert content == test_content


def test_read_novel_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_novel("nonexistent_file.txt")


def test_read_novel_large_file(tmp_path):
    test_file = tmp_path / "large_novel.txt"
    test_content = "这是很长的小说内容\n" * 100
    test_file.write_text(test_content, encoding="utf-8")

    content = read_novel(str(test_file))
    assert content == test_content


def test_read_novel_gbk_encoding(tmp_path):
    test_file = tmp_path / "gbk_novel.txt"
    test_content = "这是GBK编码的小说内容"
    test_file.write_text(test_content, encoding="gbk")

    content = read_novel(str(test_file))
    assert content == test_content


def test_read_novel_gb2312_encoding(tmp_path):
    test_file = tmp_path / "gb2312_novel.txt"
    test_content = "这是GB2312编码的小说内容"
    test_file.write_text(test_content, encoding="gb2312")

    content = read_novel(str(test_file))
    assert content == test_content

