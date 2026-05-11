from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import re

app = Flask(__name__)
CORS(app)

# 配置
MAX_DURATION = 1800  # 30分钟，防止滥用
DOWNLOAD_FOLDER = tempfile.mkdtemp()

def is_valid_youtube_url(url):
    """验证 YouTube URL"""
    patterns = [
        r'https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(www\.)?youtube\.com/shorts/[\w-]+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def get_video_info(url):
    """获取视频信息"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'author': info.get('uploader'),
        }

def get_available_formats(url):
    """获取可用的下载格式"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        formats = []
        seen = set()
        
        # 获取视频+音频格式
        for f in info.get('formats', []):
            # 跳过只有音频或只有视频的格式
            if f.get('vcodec') == 'none' or f.get('acodec') == 'none':
                continue
                
            # 创建格式标识
            height = f.get('height', 0)
            if height >= 2160:
                quality = '4K'
            elif height >= 1080:
                quality = '1080p'
            elif height >= 720:
                quality = '720p'
            elif height >= 480:
                quality = '480p'
            else:
                quality = '360p'
            
            format_key = f'{quality}_{f.get("ext", "mp4")}'
            
            if format_key in seen:
                continue
            seen.add(format_key)
            
            formats.append({
                'format_id': f['format_id'],
                'quality': quality,
                'ext': f.get('ext', 'mp4'),
                'filesize': f.get('filesize'),
                'has_video': True,
                'has_audio': True
            })
        
        # 添加音频格式
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                formats.append({
                    'format_id': f['format_id'],
                    'quality': 'audio',
                    'ext': 'mp3',
                    'filesize': f.get('filesize'),
                    'has_video': False,
                    'has_audio': True
                })
                break
        
        return formats

@app.route('/api/info', methods=['GET'])
def api_get_info():
    """API: 获取视频信息"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({'error': '缺少 URL 参数'}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({'error': '无效的 YouTube URL'}), 400
    
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/formats', methods=['GET'])
def api_get_formats():
    """API: 获取可用格式"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({'error': '缺少 URL 参数'}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({'error': '无效的 YouTube URL'}), 400
    
    try:
        formats = get_available_formats(url)
        return jsonify({'formats': formats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
    """API: 获取下载链接"""
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')
    
    if not url:
        return jsonify({'error': '缺少 URL 参数'}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({'error': '无效的 YouTube URL'}), 400
    
    try:
        # 获取视频信息
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 检查视频时长
            if info.get('duration', 0) > MAX_DURATION:
                return jsonify({'error': f'视频时长超过 {MAX_DURATION//60} 分钟限制'}), 400
            
            # 查找指定格式
            for f in info.get('formats', []):
                if f['format_id'] == format_id:
                    return jsonify({
                        'download_url': f['url'],
                        'title': info['title'],
                        'ext': f.get('ext', 'mp4')
                    })
            
            # 如果没有找到指定格式，返回最高质量
            best_format = info.get('formats', [])[-1]
            return jsonify({
                'download_url': best_format['url'],
                'title': info['title'],
                'ext': best_format.get('ext', 'mp4')
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
