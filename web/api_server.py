"""
Flask API Server for YouTube Reupload Detector Web Interface
Kết nối giữa web frontend và backend xử lý Python
"""

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
import sys
import os
from pathlib import Path
import tempfile
import pandas as pd
from datetime import datetime
import json
import threading
import queue
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import ProcessingPipeline
from src.utils import setup_logger, get_config
from database import AnalysisDatabase

logger = setup_logger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)

# Initialize database
db = AnalysisDatabase()

config = get_config('../config.yaml')
pipeline = None
current_results = None
current_job = None
cancellation_flag = threading.Event()
processing_thread = None  # Track the processing thread
cancellation_requested = False  # Simple flag for cancellation
active_clients = []  # Track active web clients

# Real-time log streaming
log_queue = queue.Queue(maxsize=1000)  # Store last 1000 log messages
log_clients = []  # List of connected SSE clients


def check_active_clients():
    """Check if any clients are still connected"""
    return len(log_clients) > 0 or len(active_clients) > 0


def auto_cancel_if_no_clients():
    """Auto-cancel processing if no clients connected"""
    if processing_thread and processing_thread.is_alive():
        if not check_active_clients():
            logger.warning("⚠️  No clients connected - auto-cancelling processing")
            cancellation_flag.set()


def cleanup_stale_clients():
    """Remove clients that haven't sent heartbeat in a while"""
    # This is called periodically to clean up dead clients
    # Active clients list is managed by heartbeat endpoint
    pass


# Background thread to monitor clients
def client_monitor():
    """Monitor active clients and auto-cancel if all disconnect"""
    import time
    while True:
        time.sleep(30)  # Check every 30 seconds
        auto_cancel_if_no_clients()


# Start client monitor thread
import threading
monitor_thread = threading.Thread(target=client_monitor, daemon=True, name="ClientMonitor")
monitor_thread.start()
logger.info("✅ Client monitor thread started")


class WebLogHandler(logging.Handler):
    """Custom log handler that streams logs to web clients"""
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'level': record.levelname,
                'message': self.format(record),
                'logger': record.name
            }

            # Add to main queue for history (remove oldest if full)
            try:
                log_queue.put_nowait(log_entry)
            except queue.Full:
                # Remove oldest and add new
                try:
                    log_queue.get_nowait()
                    log_queue.put_nowait(log_entry)
                except:
                    pass

            # Broadcast to all connected clients immediately
            dead_clients = []
            for client_queue in log_clients:
                try:
                    client_queue.put_nowait(log_entry)
                except queue.Full:
                    dead_clients.append(client_queue)
                except:
                    pass

            # Remove dead clients
            for dead in dead_clients:
                if dead in log_clients:
                    log_clients.remove(dead)

        except Exception:
            pass


# Setup web log handler
web_handler = WebLogHandler()
web_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
web_handler.setFormatter(formatter)

# Add handler to root logger to capture all logs
logging.getLogger().addHandler(web_handler)
# Also add to our logger
logger.addHandler(web_handler)


def get_pipeline():
    global pipeline
    if pipeline is None:
        logger.info("Initializing processing pipeline...")
        pipeline = ProcessingPipeline(config)
    return pipeline


def find_url_column(df):
    """
    Find URL/Link column in DataFrame
    Supports multiple column name variations, case-insensitive, with whitespace handling

    Returns: (url_column_name, error_message)
    """
    # Clean column names first
    df.columns = df.columns.str.strip()

    url_column = None
    possible_url_columns = [
        'Link', 'link', 'LINK',
        'Link YouTube', 'link youtube', 'LINK YOUTUBE',
        'URL', 'url',
        'Video URL', 'video url', 'VIDEO URL',
        'video_url', 'Video_URL'
    ]

    # Strategy 1: Exact match
    for col in possible_url_columns:
        if col in df.columns:
            url_column = col
            logger.info(f"Found URL column: '{col}' (exact match)")
            return url_column, None

    # Strategy 2: Case-insensitive match
    col_lower_map = {col.lower(): col for col in df.columns}
    for possible_col in possible_url_columns:
        if possible_col.lower() in col_lower_map:
            url_column = col_lower_map[possible_col.lower()]
            logger.info(f"Found URL column: '{url_column}' (case-insensitive)")
            return url_column, None

    # Strategy 3: Fuzzy match (contains 'link' or 'url')
    for col in df.columns:
        col_lower = col.lower()
        if 'link' in col_lower or 'url' in col_lower:
            url_column = col
            logger.info(f"Found URL column: '{col}' (fuzzy match)")
            return url_column, None

    # Not found
    available_cols = ', '.join(df.columns.tolist())
    error_msg = f'Không tìm thấy cột URL/Link. Các cột có sẵn: {available_cols}'
    logger.error(error_msg)
    return None, error_msg


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

        # Find URL column using helper function
        url_column, error_msg = find_url_column(df)
        if url_column is None:
            print(f"✗ ERROR: {error_msg}\n")
            return jsonify({'success': False, 'error': error_msg}), 400

        print(f"✓ Found URL column: '{url_column}'")

        # Get URLs and filter valid ones
        urls_raw = df[url_column].dropna().tolist()
        urls = []
        for url in urls_raw:
            url_str = str(url).strip()
            # Basic validation: must contain youtube.com or youtu.be
            if url_str and ('youtube.com' in url_str.lower() or 'youtu.be' in url_str.lower()):
                urls.append(url_str)
            elif url_str:
                logger.warning(f"Skipping invalid URL: {url_str[:50]}...")

        if not urls:
            error_msg = f'Không tìm thấy URL YouTube hợp lệ trong cột "{url_column}"'
            print(f"✗ ERROR: {error_msg}\n")
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg}), 400

        metadata = df.to_dict('records')

        print(f"✓ Found {len(urls)} valid YouTube URLs\n")
        logger.info(f"Found {len(urls)} valid YouTube URLs")

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

        # Save to database
        try:
            analysis_data = {
                'file_name': file.filename,
                'total_videos': statistics['total_videos'],
                'reupload_count': statistics['total_reuploads'],
                'reupload_percent': statistics['reupload_percentage'],
                'cluster_count': statistics['clusters'],
                'audio_threshold': audio_threshold,
                'video_threshold': video_threshold,
                'combined_threshold': combined_threshold,
                'gpu_enabled': gpu_enabled,
                'processing_time_seconds': results.get('processing_time', 0),
                'summary': {
                    'avg_similarity': statistics['average_similarity']
                }
            }

            # Add video details if available
            if 'groups' in results:
                video_list = []
                for group in results['groups']:
                    for video_data in group.get('videos', []):
                        video_list.append({
                            'video_id': video_data.get('id', ''),
                            'channel_name': video_data.get('channel', ''),
                            'title': video_data.get('title', ''),
                            'is_reupload': group.get('is_reupload', False),
                            'cluster_id': group.get('cluster_id', -1),
                            'similarity_score': video_data.get('similarity', 0)
                        })
                analysis_data['videos'] = video_list

            run_id = db.save_analysis(analysis_data)
            logger.info(f"✅ Analysis saved to database (ID: {run_id})")
            response['run_id'] = run_id
        except Exception as db_error:
            logger.error(f"Failed to save analysis to database: {db_error}")

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
    global cancellation_flag, current_job, cancellation_requested, processing_thread

    try:
        cancellation_requested = True
        cancellation_flag.set()

        print("\n" + "="*80)
        print("CANCELLATION REQUESTED - FORCE STOPPING")
        print("="*80 + "\n")

        logger.info("="*80)
        logger.info("CANCELLATION REQUESTED - Stopping all processing")
        logger.info("="*80)

        if current_job:
            current_job['status'] = 'cancelled'

        # Force terminate the processing thread if it exists
        if processing_thread and processing_thread.is_alive():
            logger.warning("Attempting to forcefully terminate processing thread...")
            try:
                import ctypes
                # Get thread ID and force terminate
                thread_id = processing_thread.ident
                if thread_id:
                    logger.info(f"Sending SystemExit to thread {thread_id}")
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(thread_id),
                        ctypes.py_object(SystemExit)
                    )
                    if res == 0:
                        logger.error("Invalid thread ID")
                    elif res > 1:
                        # Clean up if affected too many threads
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
                        logger.error("Failed to terminate thread cleanly")
                    else:
                        logger.info("✓ Thread termination signal sent successfully")
            except Exception as thread_error:
                logger.error(f"Could not terminate thread: {thread_error}")

        return jsonify({
            'success': True,
            'message': 'Processing cancellation requested - forcing termination'
        })

    except Exception as e:
        logger.error(f"Error during cancellation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/force-kill', methods=['POST'])
def force_kill_process():
    """Emergency endpoint to force kill the entire Python process and close web tab"""
    import signal
    import sys

    logger.warning("="*80)
    logger.warning("EMERGENCY FORCE KILL REQUESTED")
    logger.warning("Closing all connections and terminating server")
    logger.warning("="*80)

    print("\n" + "="*80)
    print("⚠️  EMERGENCY FORCE KILL")
    print("⚠️  Closing all connections...")
    print("⚠️  Terminating server...")
    print("⚠️  Browser tab will close automatically")
    print("="*80 + "\n")

    # Send response with instruction to close tab
    def kill_after_response():
        import time
        import sys
        import subprocess
        import platform

        time.sleep(0.5)  # Give time for response to send

        print("\n🔴 Executing FORCE KILL...")
        pid = os.getpid()

        # Force terminate all threads and processes
        try:
            # Kill all child processes if any
            import psutil
            current_process = psutil.Process(pid)
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    print(f"🔴 Killing child process {child.pid}...")
                    child.kill()
                except:
                    pass
        except ImportError:
            # psutil not available, skip child killing
            print("⚠️ psutil not available, skipping child process killing")

        # Platform-specific force kill
        system = platform.system()
        print(f"🔴 Detected OS: {system}")
        print(f"🔴 Current PID: {pid}")

        if system == 'Windows':
            # Windows: Use taskkill /F
            print("🔴 Using Windows TASKKILL...")
            try:
                subprocess.Popen(['taskkill', '/F', '/PID', str(pid)],
                               creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                pass
        else:
            # Linux/Mac: Use kill -9
            print("🔴 Using Unix kill -9...")
            try:
                subprocess.Popen(['kill', '-9', str(pid)])
            except:
                pass

        # Multiple exit methods (one of these WILL work)
        time.sleep(0.1)
        print("🔴 Executing sys.exit(1)...")
        try:
            sys.exit(1)
        except:
            pass

        print("🔴 Executing os._exit(1)...")
        os._exit(1)  # This one is guaranteed to work

    kill_thread = threading.Thread(target=kill_after_response, daemon=False)  # daemon=False to ensure execution
    kill_thread.start()

    return jsonify({
        'success': True,
        'message': 'Server terminating - browser tab will close',
        'close_tab': True  # Signal to frontend to close tab
    })


@app.route('/api/logs/stream')
def stream_logs():
    """Server-Sent Events endpoint for real-time log streaming"""
    def generate():
        # Send all existing logs first
        existing_logs = list(log_queue.queue)
        for log_entry in existing_logs:
            yield f"data: {json.dumps(log_entry)}\n\n"

        # Create client queue and register
        local_queue = queue.Queue(maxsize=100)
        log_clients.append(local_queue)

        # Track this as an active client
        client_id = id(local_queue)
        active_clients.append(client_id)
        logger.info(f"✅ Client connected (ID: {client_id}, Total: {len(active_clients)})")

        try:
            while True:
                try:
                    # Wait for new log entries
                    log_entry = local_queue.get(timeout=30)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except queue.Empty:
                    # Send keepalive ping every 30 seconds
                    yield f": keepalive\n\n"
                    # Check if processing should be cancelled
                    auto_cancel_if_no_clients()
        except GeneratorExit:
            # Client disconnected
            if local_queue in log_clients:
                log_clients.remove(local_queue)
            if client_id in active_clients:
                active_clients.remove(client_id)

            logger.warning(f"⚠️  Client disconnected (ID: {client_id}, Remaining: {len(active_clients)})")

            # Auto-cancel if no more clients
            auto_cancel_if_no_clients()

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/logs/history', methods=['GET'])
def get_log_history():
    """Get all stored logs"""
    logs = list(log_queue.queue)
    return jsonify({
        'success': True,
        'logs': logs
    })


@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """Client heartbeat to signal it's still alive"""
    client_id = request.json.get('client_id')
    if client_id and client_id not in active_clients:
        active_clients.append(client_id)

    return jsonify({
        'success': True,
        'active_clients': len(active_clients),
        'processing': processing_thread is not None and processing_thread.is_alive()
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get server status for debugging"""
    return jsonify({
        'success': True,
        'status': {
            'active_clients': len(active_clients),
            'log_clients': len(log_clients),
            'processing': processing_thread is not None and processing_thread.is_alive(),
            'cancellation_flag': cancellation_flag.is_set(),
            'current_job': current_job is not None,
            'client_ids': active_clients[:5]  # Show first 5 for privacy
        }
    })


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

        # Find URL column using helper function
        url_column, error_msg = find_url_column(df)
        if url_column is None:
            return jsonify({'error': error_msg}), 400

        # Get URLs and filter valid ones
        urls_raw = df[url_column].dropna().tolist()
        urls = []
        for url in urls_raw:
            url_str = str(url).strip()
            if url_str and ('youtube.com' in url_str.lower() or 'youtu.be' in url_str.lower()):
                urls.append(url_str)

        if not urls:
            return jsonify({'error': f'Không tìm thấy URL YouTube hợp lệ trong cột "{url_column}"'}), 400

        metadata = df.to_dict('records')

        logger.info(f"Starting processing: {len(urls)} valid YouTube videos")

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


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get analysis history with pagination"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        history = db.get_history(limit=limit, offset=offset)

        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/<int:run_id>', methods=['GET'])
def get_history_detail(run_id):
    """Get specific analysis by ID"""
    try:
        analysis = db.get_analysis_by_id(run_id)

        if analysis is None:
            return jsonify({'success': False, 'error': 'Analysis not found'}), 404

        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        logger.error(f"Error fetching analysis {run_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/<int:run_id>', methods=['DELETE'])
def delete_history(run_id):
    """Delete specific analysis"""
    try:
        success = db.delete_analysis(run_id)

        if not success:
            return jsonify({'success': False, 'error': 'Analysis not found'}), 404

        logger.info(f"✅ Analysis {run_id} deleted")
        return jsonify({
            'success': True,
            'message': 'Analysis deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting analysis {run_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get overall statistics"""
    try:
        stats = db.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/search', methods=['GET'])
def search_history():
    """Search history by query"""
    try:
        query = request.args.get('q', '')

        if not query:
            return jsonify({'success': False, 'error': 'Query parameter required'}), 400

        results = db.search_history(query)

        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        logger.error(f"Error searching history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """Get system hardware information"""
    import platform
    import os

    try:
        # Try to import psutil for detailed info
        try:
            import psutil
            has_psutil = True
        except ImportError:
            has_psutil = False
            logger.warning("psutil not available, using basic system info")

        # CPU Info
        if has_psutil:
            cpu_count = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            try:
                cpu_freq = psutil.cpu_freq()
                cpu_info = f"{cpu_count}C/{cpu_count_logical}T @ {cpu_freq.current/1000:.1f}GHz ({cpu_percent}%)"
            except:
                cpu_info = f"{cpu_count}C/{cpu_count_logical}T ({cpu_percent}%)"
        else:
            cpu_count = os.cpu_count() or 'N/A'
            cpu_info = f"{cpu_count} cores"

        # RAM Info
        if has_psutil:
            ram = psutil.virtual_memory()
            ram_total_gb = ram.total / (1024**3)
            ram_used_gb = ram.used / (1024**3)
            ram_percent = ram.percent
            ram_info = f"{ram_used_gb:.1f}/{ram_total_gb:.1f}GB ({ram_percent}%)"
        else:
            ram_info = "Install psutil for details"

        # GPU Info
        gpu_info = "CPU Only"
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                gpu_info = f"{gpu_name} ({gpu_memory:.1f}GB)"
        except:
            pass

        # Python Info
        python_version = platform.python_version()
        python_info = f"Python {python_version}"

        # OS Info
        os_info = f"{platform.system()} {platform.release()}"

        return jsonify({
            'success': True,
            'system': {
                'cpu': cpu_info,
                'ram': ram_info,
                'gpu': gpu_info,
                'python': python_info,
                'os': os_info
            }
        })
    except Exception as e:
        logger.error(f"Error fetching system info: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Return basic fallback info
        try:
            import platform
            return jsonify({
                'success': True,
                'system': {
                    'cpu': f"{os.cpu_count() or 'N/A'} cores",
                    'ram': 'N/A',
                    'gpu': 'N/A',
                    'python': f"Python {platform.python_version()}",
                    'os': f"{platform.system()} {platform.release()}"
                }
            })
        except:
            return jsonify({
                'success': False,
                'error': str(e),
                'system': {
                    'cpu': 'N/A',
                    'ram': 'N/A',
                    'gpu': 'N/A',
                    'python': 'N/A',
                    'os': 'N/A'
                }
            }), 500


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("YouTube Reupload Detector - Web Server Starting...")
    logger.info("=" * 80)
    logger.info("Access web interface at: http://localhost:5000")
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 80)

    app.run(host='0.0.0.0', port=5000, debug=True)
