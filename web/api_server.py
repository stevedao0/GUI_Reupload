"""
Flask API Server for YouTube Reupload Detector Web Interface
Kết nối giữa web frontend và backend xử lý Python
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import sys
import os
from pathlib import Path
import tempfile
import pandas as pd
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import ProcessingPipeline
from src.utils import setup_logger, get_config

logger = setup_logger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)

config = get_config('../config.yaml')
pipeline = None
current_results = None


def get_pipeline():
    global pipeline
    if pipeline is None:
        logger.info("Initializing processing pipeline...")
        pipeline = ProcessingPipeline(config)
    return pipeline


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Invalid file format. Only .xlsx and .xls allowed'}), 400

        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)

        df = pd.read_excel(file_path)

        required_columns = ['Link YouTube', 'Code']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                'error': f'Missing required columns: {", ".join(missing_columns)}'
            }), 400

        urls = df['Link YouTube'].dropna().tolist()
        codes = df['Code'].dropna().unique().tolist()

        preview_data = {
            'totalVideos': len(urls),
            'totalCodes': len(codes),
            'filePath': file_path,
            'columns': df.columns.tolist()
        }

        logger.info(f"File uploaded: {file.filename} ({len(urls)} videos, {len(codes)} codes)")

        return jsonify(preview_data)

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/process', methods=['POST'])
def process_videos():
    global current_results

    try:
        data = request.json
        file_path = data.get('filePath')
        config_overrides = data.get('config', {})

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 400

        df = pd.read_excel(file_path)

        urls = df['Link YouTube'].dropna().tolist()
        metadata = df.to_dict('records')

        logger.info(f"Starting processing: {len(urls)} videos")

        current_config = config.copy()
        if 'audioThreshold' in config_overrides:
            current_config['thresholds']['audio_similarity'] = config_overrides['audioThreshold']
        if 'videoThreshold' in config_overrides:
            current_config['thresholds']['video_similarity'] = config_overrides['videoThreshold']
        if 'combinedThreshold' in config_overrides:
            current_config['thresholds']['combined_similarity'] = config_overrides['combinedThreshold']
        if 'gpuEnabled' in config_overrides:
            current_config['gpu']['enabled'] = config_overrides['gpuEnabled']

        pipeline_instance = ProcessingPipeline(current_config)

        def progress_callback(current, total, status):
            logger.info(f"Progress: {current}/{total} - {status}")

        def log_callback(message):
            logger.info(message)

        results = pipeline_instance.process(
            urls=urls,
            metadata=metadata,
            progress_callback=progress_callback,
            log_callback=log_callback
        )

        current_results = results

        statistics = results['statistics']

        response = {
            'success': True,
            'statistics': {
                'totalVideos': statistics['total_videos'],
                'reuploads': statistics['total_reuploads'],
                'percentage': round(statistics['reupload_percentage'], 1),
                'clusters': statistics['clusters'],
                'averageSimilarity': round(statistics['average_similarity'] * 100, 1)
            }
        }

        logger.info(f"Processing complete: {statistics['total_reuploads']} reuploads found")

        return jsonify(response)

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['GET'])
def export_results():
    global current_results

    try:
        if current_results is None:
            return jsonify({'error': 'No results to export'}), 400

        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(temp_dir, f'reupload_results_{timestamp}.xlsx')

        pipeline_instance = get_pipeline()
        pipeline_instance.export_results(current_results, output_path)

        logger.info(f"Results exported to: {output_path}")

        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'reupload_results_{timestamp}.xlsx'
        )

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        'status': 'ready',
        'version': '1.3.0',
        'gpuAvailable': config.get('gpu.enabled', False)
    })


@app.route('/api/config', methods=['GET'])
def get_config_api():
    return jsonify({
        'audioThreshold': config.get('thresholds.audio_similarity', 0.65),
        'videoThreshold': config.get('thresholds.video_similarity', 0.75),
        'combinedThreshold': config.get('thresholds.combined_similarity', 0.70),
        'gpuEnabled': config.get('gpu.enabled', True)
    })


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("YouTube Reupload Detector - Web Server Starting...")
    logger.info("=" * 80)
    logger.info("Access web interface at: http://localhost:5000")
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 80)

    app.run(host='0.0.0.0', port=5000, debug=True)
