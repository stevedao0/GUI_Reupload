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
import threading

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import ProcessingPipeline
from src.utils import setup_logger, get_config

logger = setup_logger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)

config = get_config('../config.yaml')
pipeline = None
current_results = None
current_job = None
cancellation_flag = threading.Event()


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


@app.route('/api/analyze', methods=['POST'])
def analyze_videos():
    global current_results, current_job, cancellation_flag

    cancellation_flag.clear()

    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return jsonify({'success': False, 'error': 'Invalid file format'}), 400

        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)

        df = pd.read_excel(file_path) if file.filename.endswith(('.xlsx', '.xls')) else pd.read_csv(file_path)

        print("\n" + "="*80)
        print("FILE ANALYSIS")
        print("="*80)
        print(f"File: {file.filename}")
        print(f"Total rows: {len(df)}")
        print(f"Columns: {df.columns.tolist()}")
        print("="*80 + "\n")

        logger.info(f"File columns: {df.columns.tolist()}")
        logger.info(f"Total rows: {len(df)}")

        url_column = None
        possible_url_columns = ['Link', 'link', 'Link YouTube', 'link youtube', 'URL', 'url', 'Video URL', 'video_url']
        for col in possible_url_columns:
            if col in df.columns:
                url_column = col
                print(f"✓ Found URL column: '{col}'")
                logger.info(f"Found URL column: {col}")
                break

        if url_column is None:
            available_cols = ', '.join(df.columns.tolist())
            error_msg = f'Không tìm thấy cột URL. Các cột có sẵn: {available_cols}'
            print(f"✗ ERROR: {error_msg}\n")
            return jsonify({'success': False, 'error': error_msg}), 400

        urls = df[url_column].dropna().tolist()
        metadata = df.to_dict('records')

        print(f"✓ Found {len(urls)} video URLs\n")
        logger.info(f"Found {len(urls)} video URLs")

        audio_threshold = float(request.form.get('audio_threshold', 0.65))
        video_threshold = float(request.form.get('video_threshold', 0.75))
        combined_threshold = float(request.form.get('combined_threshold', 0.70))
        gpu_enabled = request.form.get('gpu_enabled', 'true').lower() == 'true'

        print("="*80)
        print("STARTING VIDEO ANALYSIS")
        print("="*80)
        print(f"Total videos: {len(urls)}")
        print(f"Audio threshold: {audio_threshold}")
        print(f"Video threshold: {video_threshold}")
        print(f"Combined threshold: {combined_threshold}")
        print(f"GPU enabled: {gpu_enabled}")
        print("="*80 + "\n")

        logger.info("="*80)
        logger.info("STARTING VIDEO ANALYSIS")
        logger.info("="*80)
        logger.info(f"Total videos: {len(urls)}")
        logger.info(f"Audio threshold: {audio_threshold}")
        logger.info(f"Video threshold: {video_threshold}")
        logger.info(f"Combined threshold: {combined_threshold}")
        logger.info(f"GPU enabled: {gpu_enabled}")
        logger.info("="*80)

        current_config = config.all.copy()
        current_config['thresholds']['audio_similarity'] = audio_threshold
        current_config['thresholds']['video_similarity'] = video_threshold
        current_config['thresholds']['combined_similarity'] = combined_threshold
        current_config['gpu']['enabled'] = gpu_enabled

        pipeline_instance = ProcessingPipeline(current_config)

        def progress_callback(current, total, status):
            if cancellation_flag.is_set():
                raise Exception("Processing cancelled by user")
            print(f"[{current}/{total}] {status}")
            logger.info(f"Progress: {current}/{total} - {status}")

        def log_callback(message):
            if cancellation_flag.is_set():
                raise Exception("Processing cancelled by user")
            print(f"  → {message}")
            logger.info(message)

        def is_cancelled():
            return cancellation_flag.is_set()

        job_id = 'job_' + datetime.now().strftime('%Y%m%d_%H%M%S')
        current_job = {'id': job_id, 'status': 'running', 'progress': 0}

        results = pipeline_instance.process(
            urls=urls,
            metadata=metadata,
            progress_callback=progress_callback,
            log_callback=log_callback,
            is_cancelled=is_cancelled
        )

        current_job = None

        current_results = results

        statistics = results['statistics']

        response = {
            'success': True,
            'job_id': job_id,
            'results': {
                'total_videos': statistics['total_videos'],
                'reupload_count': statistics['total_reuploads'],
                'reupload_percent': round(statistics['reupload_percentage'], 1),
                'cluster_count': statistics['clusters'],
                'avg_similarity': round(statistics['average_similarity'] * 100, 1)
            }
        }

        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print(f"Total videos: {statistics['total_videos']}")
        print(f"Reuploads found: {statistics['total_reuploads']}")
        print(f"Reupload percentage: {statistics['reupload_percentage']:.1f}%")
        print(f"Clusters: {statistics['clusters']}")
        print(f"Average similarity: {statistics['average_similarity']*100:.1f}%")
        print("="*80 + "\n")

        logger.info("="*80)
        logger.info("ANALYSIS COMPLETE")
        logger.info(f"Total videos: {statistics['total_videos']}")
        logger.info(f"Reuploads found: {statistics['total_reuploads']}")
        logger.info(f"Reupload percentage: {statistics['reupload_percentage']:.1f}%")
        logger.info(f"Clusters: {statistics['clusters']}")
        logger.info(f"Average similarity: {statistics['average_similarity']*100:.1f}%")
        logger.info("="*80)

        return jsonify(response)

    except Exception as e:
        print("\n" + "="*80)
        print(f"ERROR: {e}")
        print("="*80 + "\n")
        logger.error("="*80)
        logger.error(f"ERROR: {e}")
        logger.error("="*80)
        logger.error(f"Processing error: {e}", exc_info=True)
        current_job = None
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cancel', methods=['POST'])
def cancel_processing():
    global cancellation_flag, current_job

    try:
        cancellation_flag.set()

        print("\n" + "="*80)
        print("CANCELLATION REQUESTED")
        print("="*80 + "\n")

        logger.info("="*80)
        logger.info("CANCELLATION REQUESTED - Stopping all processing")
        logger.info("="*80)

        if current_job:
            current_job['status'] = 'cancelled'

        return jsonify({
            'success': True,
            'message': 'Processing cancellation requested'
        })

    except Exception as e:
        logger.error(f"Error during cancellation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/job/status', methods=['GET'])
def get_job_status():
    global current_job

    if current_job:
        return jsonify({
            'success': True,
            'job': current_job
        })
    else:
        return jsonify({
            'success': True,
            'job': None
        })


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

        def is_cancelled():
            return cancellation_requested

        results = pipeline_instance.process(
            urls=urls,
            metadata=metadata,
            progress_callback=progress_callback,
            log_callback=log_callback,
            is_cancelled=is_cancelled
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

    except RuntimeError as e:
        if "cancelled" in str(e).lower():
            logger.info("Processing cancelled by user")
            return jsonify({'error': 'Processing cancelled by user', 'cancelled': True}), 499
        logger.error(f"Processing error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/<job_id>', methods=['GET'])
def export_results(job_id):
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


@app.route('/api/status/<job_id>', methods=['GET'])
def get_job_status_by_id(job_id):
    global current_results

    if current_results is None:
        return jsonify({
            'status': 'processing',
            'progress': {
                'percent': 0,
                'step': 0,
                'message': 'Đang khởi tạo...'
            }
        })

    statistics = current_results.get('statistics', {})

    return jsonify({
        'status': 'completed',
        'results': {
            'total_videos': statistics.get('total_videos', 0),
            'reupload_count': statistics.get('total_reuploads', 0),
            'reupload_percent': round(statistics.get('reupload_percentage', 0), 1),
            'cluster_count': statistics.get('clusters', 0),
            'avg_similarity': round(statistics.get('average_similarity', 0) * 100, 1)
        }
    })


@app.route('/api/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    logger.info(f"Cancelling job: {job_id}")
    return jsonify({'success': True})


@app.route('/api/status', methods=['GET'])
def get_server_status():
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
