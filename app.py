from flask import Flask, request, jsonify, send_file
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
            'formats': info.get('formats', [])
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
        
        for f in info.get('formats', []):
            # 跳过只有音频或只有视频的格式
            if f.get('vcodec') == 'none' or f.get('acodec') == 'none':
                continue
                
            # 创建格式标识
            format_id = f'{f.get("height", 0)}p_{f.get("ext", "mp4")}'
            
            if format_id in seen:
                continue
            seen.add(format_id)
            
            formats.append({
                'format_id': f['format_id'],
                'quality': f'{f.get("height", 0)}p',
                'ext': f.get('ext', 'mp4'),
                'filesize': f.get('filesize'),
                'vcodec': f.get('vcodec'),
                'acodec': f.get('acodec'),
                'fps': f.get('fps'),
                'has_video': f.get('vcodec') != 'none',
                'has_audio': f.get('acodec') != 'none'
            })
        
        # 添加音频格式
        audio_formats = []
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                audio_formats.append({
                    'format_id': f['format_id'],
                    'quality': 'audio',
                    'ext': 'mp3',
                    'filesize': f.get('filesize'),
                    'has_video': False,
                    'has_audio': True
                })
                break  # 只需要一个音频格式
        
        formats.extend(audio_formats)
        
        # 按质量排序
        quality_order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, '360p': 0, 'audio': -1}
        formats.sort(key=lambda x: quality_order.get(x['quality'], 0), reverse=True)
        
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
    """API: 下载视频"""
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
            
            # 生成下载 URL
            # 注意：由于 yt-dlp 需要下载到服务器，这里返回直接的 YouTube 流 URL
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
