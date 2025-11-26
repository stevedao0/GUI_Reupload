class YouTubeContentDetector {
    constructor() {
        this.uploadedFile = null;
        this.isProcessing = false;
        this.startTime = null;
        this.timerInterval = null;
        this.jobId = null;
        this.logEventSource = null;
        this.autoScroll = true;
        this.clientId = 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this.heartbeatInterval = null;

        this.initElements();
        this.attachEventListeners();
        this.initSliders();
        this.initConsole();
        this.setupCleanup();
        this.startHeartbeat();
    }

    setupCleanup() {
        // Cancel processing when tab/window closes
        window.addEventListener('beforeunload', (e) => {
            if (this.isProcessing) {
                // Cancel the job
                this.cancelAnalysis(true); // silent = true

                // Show confirmation dialog
                e.preventDefault();
                e.returnValue = 'Phân tích đang chạy. Bạn có chắc muốn thoát?';
                return e.returnValue;
            }
        });

        // Cleanup on page unload
        window.addEventListener('unload', () => {
            this.cleanup();
        });

        // Handle visibility change (tab switch)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Tab hidden but don't cancel
                console.log('Tab hidden');
            } else {
                // Tab visible again
                console.log('Tab visible');
            }
        });
    }

    startHeartbeat() {
        // Send heartbeat every 10 seconds to signal client is alive
        this.heartbeatInterval = setInterval(() => {
            fetch('/api/heartbeat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ client_id: this.clientId })
            }).catch(err => console.warn('Heartbeat failed:', err));
        }, 10000);
    }

    cleanup() {
        // Stop heartbeat
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }

        // Close SSE connection
        if (this.logEventSource) {
            this.logEventSource.close();
            this.logEventSource = null;
        }

        // Cancel any ongoing processing
        if (this.isProcessing) {
            this.cancelAnalysis(true);
        }

        console.log('Cleanup complete');
    }

    initElements() {
        this.uploadBox = document.getElementById('uploadBox');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfoCard = document.getElementById('fileInfoCard');
        this.fileName = document.getElementById('fileName');
        this.fileStats = document.getElementById('fileStats');
        this.removeBtn = document.getElementById('removeBtn');

        this.settingsPanel = document.getElementById('settingsPanel');
        this.audioThreshold = document.getElementById('audioThreshold');
        this.videoThreshold = document.getElementById('videoThreshold');
        this.combinedThreshold = document.getElementById('combinedThreshold');
        this.gpuEnabled = document.getElementById('gpuEnabled');
        this.audioValue = document.getElementById('audioValue');
        this.videoValue = document.getElementById('videoValue');
        this.combinedValue = document.getElementById('combinedValue');
        this.analyzeBtn = document.getElementById('analyzeBtn');

        this.compareEmpty = document.getElementById('compareEmpty');
        this.progressCard = document.getElementById('progressCard');
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
        this.currentStep = document.getElementById('currentStep');
        this.elapsedTime = document.getElementById('elapsedTime');
        this.cancelBtn = document.getElementById('cancelBtn');
        this.forceKillBtn = document.getElementById('forceKillBtn');

        this.resultsContainer = document.getElementById('resultsContainer');
        this.totalVideos = document.getElementById('totalVideos');
        this.reuploadCount = document.getElementById('reuploadCount');
        this.reuploadPercent = document.getElementById('reuploadPercent');
        this.clusterCount = document.getElementById('clusterCount');
        this.exportBtn = document.getElementById('exportBtn');

        this.statAudioThreshold = document.getElementById('statAudioThreshold');
        this.statVideoThreshold = document.getElementById('statVideoThreshold');
        this.statCombinedThreshold = document.getElementById('statCombinedThreshold');
        this.statGpuStatus = document.getElementById('statGpuStatus');

        this.tabBtns = document.querySelectorAll('.tab-btn');
        this.tabPanes = document.querySelectorAll('.tab-pane');

        this.consolePanel = document.getElementById('consolePanel');
        this.consoleBody = document.getElementById('consoleBody');
        this.clearLogsBtn = document.getElementById('clearLogsBtn');
        this.toggleConsoleBtn = document.getElementById('toggleConsoleBtn');
    }

    attachEventListeners() {
        this.uploadBtn.addEventListener('click', () => this.fileInput.click());
        this.uploadBox.addEventListener('click', (e) => {
            if (e.target === this.uploadBox || e.target.closest('.upload-icon-wrapper') || e.target.closest('h3') || e.target.closest('p')) {
                this.fileInput.click();
            }
        });
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        this.removeBtn.addEventListener('click', () => this.clearFile());

        this.uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadBox.classList.add('drag-over');
        });

        this.uploadBox.addEventListener('dragleave', () => {
            this.uploadBox.classList.remove('drag-over');
        });

        this.uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadBox.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });

        this.analyzeBtn.addEventListener('click', () => this.startAnalysis());
        this.cancelBtn.addEventListener('click', () => this.cancelAnalysis());
        this.forceKillBtn.addEventListener('click', () => this.forceKillServer());
        this.exportBtn.addEventListener('click', () => this.exportResults());

        this.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
    }

    initSliders() {
        this.audioThreshold.addEventListener('input', (e) => {
            const value = Math.round(e.target.value * 100);
            this.audioValue.textContent = `${value}%`;
            this.statAudioThreshold.textContent = `${value}%`;
        });

        this.videoThreshold.addEventListener('input', (e) => {
            const value = Math.round(e.target.value * 100);
            this.videoValue.textContent = `${value}%`;
            this.statVideoThreshold.textContent = `${value}%`;
        });

        this.combinedThreshold.addEventListener('input', (e) => {
            const value = Math.round(e.target.value * 100);
            this.combinedValue.textContent = `${value}%`;
            this.statCombinedThreshold.textContent = `${value}%`;
        });

        this.gpuEnabled.addEventListener('change', (e) => {
            this.statGpuStatus.textContent = e.target.checked ? 'Enabled' : 'Disabled';
            this.statGpuStatus.parentElement.parentElement.querySelector('.stat-icon').style.opacity = e.target.checked ? '1' : '0.5';
        });

        // Initialize stat cards with current values
        this.statAudioThreshold.textContent = `${Math.round(this.audioThreshold.value * 100)}%`;
        this.statVideoThreshold.textContent = `${Math.round(this.videoThreshold.value * 100)}%`;
        this.statCombinedThreshold.textContent = `${Math.round(this.combinedThreshold.value * 100)}%`;
        this.statGpuStatus.textContent = this.gpuEnabled.checked ? 'Enabled' : 'Disabled';
    }

    switchTab(tabName) {
        this.tabBtns.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        this.tabPanes.forEach(pane => {
            if (pane.dataset.pane === tabName) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }

    handleFile(file) {
        if (!file.name.match(/\.(xlsx|xls|csv)$/)) {
            alert('Vui lòng chọn file Excel (.xlsx, .xls) hoặc CSV');
            return;
        }

        this.uploadedFile = file;
        this.parseExcelFile(file);
    }

    parseExcelFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet);

                const videoCount = jsonData.length;
                const fileSize = this.formatFileSize(file.size);

                this.fileName.textContent = file.name;
                this.fileStats.textContent = `${videoCount} videos • ${fileSize}`;
                this.fileInfoCard.style.display = 'flex';
                this.settingsPanel.style.display = 'block';

                console.log(`File loaded: ${videoCount} videos`);
            } catch (error) {
                alert('Lỗi khi đọc file. Vui lòng kiểm tra định dạng file.');
                console.error(error);
            }
        };
        reader.readAsArrayBuffer(file);
    }

    clearFile() {
        this.uploadedFile = null;
        this.fileInfoCard.style.display = 'none';
        this.settingsPanel.style.display = 'none';
        this.fileInput.value = '';
    }

    async startAnalysis() {
        if (!this.uploadedFile || this.isProcessing) return;

        this.isProcessing = true;
        this.switchTab('compare');

        // Show progress, hide empty state
        this.compareEmpty.style.display = 'none';
        this.progressCard.style.display = 'block';

        this.startTime = Date.now();
        this.timerInterval = setInterval(() => this.updateTimer(), 1000);

        const formData = new FormData();
        formData.append('file', this.uploadedFile);
        formData.append('audio_threshold', this.audioThreshold.value);
        formData.append('video_threshold', this.videoThreshold.value);
        formData.append('combined_threshold', this.combinedThreshold.value);
        formData.append('gpu_enabled', this.gpuEnabled.checked);

        try {
            this.progressText.textContent = 'Đang tải lên file và bắt đầu phân tích...';
            this.progressBar.style.width = '5%';
            this.currentStep.textContent = '1';

            // Update progress percentage display
            const progressPercentage = this.progressCard.querySelector('.progress-percentage');
            if (progressPercentage) {
                progressPercentage.textContent = '5%';
            }

            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.jobId = result.job_id;
                this.isProcessing = false;
                clearInterval(this.timerInterval);
                this.showResults(result.results);
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (error) {
            const errorMsg = error.message || 'Unknown error';
            if (errorMsg.includes('cancelled') || errorMsg.includes('Cancelled')) {
                alert('Đã hủy phân tích');
            } else {
                alert('Lỗi khi phân tích: ' + errorMsg);
            }
            console.error(error);
            this.cancelAnalysis();
        }
    }

    async pollProgress() {
        // Không cần poll vì xử lý đồng bộ
    }

    updateProgress(progress) {
        const percent = Math.round(progress.percent || 0);
        this.progressBar.style.width = `${percent}%`;
        this.progressText.textContent = progress.message || 'Đang xử lý...';
        this.currentStep.textContent = `${progress.step || 0}/6`;

        // Update progress percentage display
        const progressPercentage = this.progressCard.querySelector('.progress-percentage');
        if (progressPercentage) {
            progressPercentage.textContent = `${percent}%`;
        }
    }

    showResults(results) {
        this.switchTab('results');

        this.totalVideos.textContent = results.total_videos || 0;
        this.reuploadCount.textContent = results.reupload_count || 0;
        this.reuploadPercent.textContent = `${results.reupload_percent || 0}%`;
        this.clusterCount.textContent = results.cluster_count || 0;

        const statTotal = document.getElementById('statTotalVideos');
        const statReuploads = document.getElementById('statReuploads');
        if (statTotal) statTotal.textContent = results.total_videos || 0;
        if (statReuploads) statReuploads.textContent = results.reupload_count || 0;

        console.log('Analysis complete:', results);
    }

    async cancelAnalysis(silent = false) {
        if (!silent && !confirm('Bạn có chắc muốn hủy phân tích? Tất cả tiến trình sẽ bị mất.')) {
            return;
        }

        console.log('Cancelling analysis...');

        if (!silent) {
            this.progressText.textContent = 'Đang hủy... (đợi 3 giây)';
            this.cancelBtn.disabled = true;
            this.cancelBtn.textContent = 'Đang hủy...';

            // Show force kill button immediately
            this.forceKillBtn.style.display = 'block';
            this.showNotification('⚠️ Nếu không dừng, click "Force Kill Server"', 'warning');
        }

        try {
            const response = await fetch('/api/cancel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ client_id: this.clientId })
            });

            const result = await response.json();

            if (result.success) {
                console.log('Cancellation request sent');
                if (!silent) {
                    this.progressText.textContent = 'Đã gửi yêu cầu hủy. Nếu vẫn chạy, click Force Kill.';
                }
            } else {
                console.error('Cancellation failed:', result.error);
                if (!silent) {
                    this.showNotification('Lỗi khi hủy: ' + result.error, 'error');
                }
            }
        } catch (error) {
            console.error('Error canceling:', error);
            if (!silent) {
                this.showNotification('Không thể hủy: ' + error.message, 'error');
            }
        }

        // Don't reset immediately - keep showing force kill option
    }

    async forceKillServer() {
        if (!confirm('⚠️ CẢNH BÁO: Thao tác này sẽ:\n\n1. DỪNG HOÀN TOÀN server\n2. ĐÓNG tab trình duyệt này\n3. Ngắt mọi kết nối\n\nBạn sẽ phải khởi động lại bằng tay.\n\nBạn có chắc chắn?')) {
            return;
        }

        // Show full screen overlay with message
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
            z-index: 999999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        `;

        overlay.innerHTML = `
            <div style="text-align: center; animation: fadeIn 0.3s ease;">
                <div style="font-size: 80px; margin-bottom: 30px;">⚠️</div>
                <h1 style="font-size: 48px; margin-bottom: 20px; font-weight: 700;">FORCE KILL</h1>
                <p style="font-size: 24px; margin-bottom: 30px; opacity: 0.9;">Đang dừng server...</p>
                <div style="width: 300px; height: 6px; background: rgba(255,255,255,0.3); border-radius: 10px; overflow: hidden; margin: 0 auto;">
                    <div style="width: 100%; height: 100%; background: white; animation: progress 1.3s ease-in-out;"></div>
                </div>
                <p style="font-size: 16px; margin-top: 40px; opacity: 0.8;">Đang đóng...</p>
            </div>
            <style>
                @keyframes fadeIn {
                    from { opacity: 0; transform: scale(0.8); }
                    to { opacity: 1; transform: scale(1); }
                }
                @keyframes progress {
                    from { transform: translateX(-100%); }
                    to { transform: translateX(0); }
                }
            </style>
        `;

        document.body.appendChild(overlay);

        // Close tab immediately after 1.5 seconds (don't wait for response)
        setTimeout(() => {
            // Try to close the tab
            window.close();

            // If window.close() fails, redirect to blank page
            setTimeout(() => {
                window.location.href = 'about:blank';
            }, 300);
        }, 1500);

        // Send kill request (but don't wait for response since server will die)
        try {
            fetch('/api/force-kill', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                // Important: don't wait for response
                keepalive: false
            }).catch(() => {
                // Ignore all errors - server is dying, this is expected
            });
        } catch (error) {
            // Ignore - server will be dead anyway
        }
    }

    initConsole() {
        this.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        this.toggleConsoleBtn.addEventListener('click', () => this.toggleConsole());

        this.consoleBody.addEventListener('scroll', () => {
            const isAtBottom = this.consoleBody.scrollHeight - this.consoleBody.scrollTop <= this.consoleBody.clientHeight + 50;
            this.autoScroll = isAtBottom;
        });

        this.connectLogStream();
    }

    connectLogStream() {
        if (this.logEventSource) {
            this.logEventSource.close();
        }

        this.logEventSource = new EventSource('/api/logs/stream');

        this.logEventSource.onmessage = (event) => {
            try {
                const logEntry = JSON.parse(event.data);
                this.addLogLine(logEntry);
            } catch (error) {
                console.error('Failed to parse log:', error);
            }
        };

        this.logEventSource.onerror = (error) => {
            console.error('Log stream error:', error);
            setTimeout(() => this.connectLogStream(), 5000);
        };
    }

    addLogLine(logEntry) {
        const placeholder = this.consoleBody.querySelector('.console-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const line = document.createElement('div');
        line.className = 'console-line';

        line.innerHTML = `
            <span class="console-timestamp">${logEntry.timestamp}</span>
            <span class="console-level ${logEntry.level}">${logEntry.level}</span>
            <span class="console-message">${this.escapeHtml(logEntry.message)}</span>
        `;

        this.consoleBody.appendChild(line);

        if (this.autoScroll) {
            this.consoleBody.scrollTop = this.consoleBody.scrollHeight;
        }

        const maxLines = 1000;
        const lines = this.consoleBody.querySelectorAll('.console-line');
        if (lines.length > maxLines) {
            lines[0].remove();
        }
    }

    clearLogs() {
        this.consoleBody.innerHTML = '<div class="console-placeholder">Logs cleared. Waiting for new logs...</div>';
    }

    toggleConsole() {
        this.consolePanel.classList.toggle('collapsed');
        const svg = this.toggleConsoleBtn.querySelector('svg polyline');
        if (this.consolePanel.classList.contains('collapsed')) {
            svg.setAttribute('points', '6 9 12 15 18 9');
        } else {
            svg.setAttribute('points', '18 15 12 9 6 15');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: ${type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-weight: 500;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    async exportResults() {
        if (!this.jobId) {
            alert('Không có kết quả để xuất');
            return;
        }

        try {
            const response = await fetch(`/api/export/${this.jobId}`);
            const blob = await response.blob();

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `youtube_detection_${Date.now()}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            console.log('Results exported successfully');
        } catch (error) {
            alert('Lỗi khi xuất kết quả: ' + error.message);
            console.error(error);
        }
    }

    updateTimer() {
        if (!this.startTime) return;
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        this.elapsedTime.textContent = `${elapsed}s`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new YouTubeContentDetector();
    console.log('YouTube Content Detector initialized');
});
