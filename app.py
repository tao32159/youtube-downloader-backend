from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
import os

app = Flask(__name__)
CORS(app)

# 配置
MAX_DURATION = 1800  # 30分钟

def is_valid_youtube_url(url):
    """验证 YouTube URL"""
    patterns = [
        r'https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(www\.)?youtube\.com/shorts/[\w-]+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def extract_video_id(url):
    """提取视频ID"""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/api/info', methods=['GET'])
def api_get_info():
    """API: 获取视频信息"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({'error': '缺少 URL 参数'}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({'error': '无效的 YouTube URL'}), 400
    
    try:
        video_id = extract_video_id(url)
        
        # 使用 Invidious API 获取视频信息
        invidious_instances = [
            'https://invidious.nerdvpn.de',
            'https://inv.nadeko.net',
            'https://invidious.poast.org',
        ]
        
        info = None
        for instance in invidious_instances:
            try:
                api_url = f'{instance}/api/v1/videos/{video_id}'
                resp = requests.get(api_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    data = resp.json()
                    info = {
                        'id': data.get('videoId'),
                        'title': data.get('title'),
                        'duration': data.get('lengthSeconds', 0),
                        'thumbnail': data.get('thumbnailUrls', [''])[0] if data.get('thumbnailUrls') else f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                        'author': data.get('author'),
                    }
                    break
            except Exception as e:
                continue
        
        if info:
            return jsonify(info)
        else:
            return jsonify({'error': '无法获取视频信息'}), 500
            
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
        video_id = extract_video_id(url)
        
        # 使用 Invidious API
        invidious_instances = [
            'https://invidious.nerdvpn.de',
            'https://inv.nadeko.net',
            'https://invidious.poast.org',
        ]
        
        formats = []
        for instance in invidious_instances:
            try:
                api_url = f'{instance}/api/v1/videos/{video_id}'
                resp = requests.get(api_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # 提取流信息
                    streamingData = data.get('streamingData', {})
                    
                    # 视频流
                    for f in streamingData.get('formats', []):
                        height = f.get('height', 0)
                        if height >= 2160:
                            quality = '4K'
                        elif height >= 1080:
                            quality = '1080p'
                        elif height >= 720:
                            quality = '720p'
                        elif height >= 480:
                            quality = '480p'
                        elif height >= 360:
                            quality = '360p'
                        else:
                            quality = '240p'
                        
                        formats.append({
                            'format_id': f.get('itag'),
                            'quality': quality,
                            'ext': f.get('container') or 'mp4',
                            'filesize': f.get('contentLength'),
                            'url': f.get('url'),
                            'has_video': True,
                            'has_audio': f.get('hasAudio', True)
                        })
                    
                    # 自适应流（视频+音频分开）
                    for f in streamingData.get('adaptiveFormats', []):
                        mimeType = f.get('mimeType', '')
                        if 'video' in mimeType:
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
                            
                            # 去重
                            if not any(x['quality'] == quality and x['has_video'] for x in formats):
                                formats.append({
                                    'format_id': f.get('itag'),
                                    'quality': quality,
                                    'ext': f.get('container') or 'mp4',
                                    'filesize': f.get('contentLength'),
                                    'url': f.get('url'),
                                    'has_video': True,
                                    'has_audio': False
                                })
                        elif 'audio' in mimeType:
                            formats.append({
                                'format_id': f.get('itag'),
                                'quality': 'audio',
                                'ext': 'mp3',
                                'filesize': f.get('contentLength'),
                                'url': f.get('url'),
                                'has_video': False,
                                'has_audio': True
                            })
                    
                    break
            except Exception as e:
                continue
        
        if formats:
            return jsonify({'formats': formats})
        else:
            return jsonify({'error': '无法获取格式信息'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def api_download():
    """API: 获取下载链接"""
    url = request.args.get('url')
    format_id = request.args.get('format_id')
    
    if not url:
        return jsonify({'error': '缺少 URL 参数'}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({'error': '无效的 YouTube URL'}), 400
    
    try:
        video_id = extract_video_id(url)
        
        # 如果指定了 format_id，直接返回对应的下载链接
        if format_id:
            # 先尝试从缓存/格式列表获取
            formats_resp = api_get_formats()
            # 这里简化处理，直接返回
            pass
        
        # 使用 Invidious API 获取下载链接
        invidious_instances = [
            'https://invidious.nerdvpn.de',
            'https://inv.nadeko.net',
            'https://invidious.poast.org',
        ]
        
        for instance in invidious_instances:
            try:
                api_url = f'{instance}/api/v1/videos/{video_id}'
                resp = requests.get(api_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    data = resp.json()
                    streamingData = data.get('streamingData', {})
                    
                    # 优先返回最高质量的直接下载链接
                    formats = streamingData.get('formats', []) + streamingData.get('adaptiveFormats', [])
                    
                    # 找1080p或最高质量
                    best = None
                    for f in formats:
                        if f.get('url') and f.get('hasAudio'):
                            height = f.get('height', 0)
                            if height >= 1080 or (not best):
                                best = f
                                break
                    
                    if best:
                        return jsonify({
                            'download_url': best.get('url'),
                            'title': data.get('title'),
                            'ext': best.get('container') or 'mp4'
                        })
                    
                    break
            except:
                continue
        
        return jsonify({'error': '无法获取下载链接'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok'})

@app.route('/')
def index():
    """首页"""
    return jsonify({
        'name': 'YouTube Downloader API',
        'version': '1.0',
        'endpoints': ['/api/info', '/api/formats', '/api/download', '/health']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
