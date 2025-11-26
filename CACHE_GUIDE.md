# 💾 File Cache & Resume Guide

**Quick reference for managing downloaded files**

---

## ⚠️ **IMPORTANT: Preventing File Loss**

### **Default Behavior (SAFE)**

```yaml
# config.yaml
download:
  keep_files: true  # ✅ Files are KEPT by default
```

**What this means:**
- ✅ All downloaded files are saved in `temp_downloads/`
- ✅ Files are reused on next run (cache = instant, no re-download)
- ✅ Re-runs are 75%+ faster
- ✅ Safe to stop and resume processing

---

## 🚨 **If Files Were Deleted**

### **Why It Happened:**

1. **Config was set to delete:**
   ```yaml
   keep_files: false  # ❌ This deletes everything!
   ```

2. **Old version** before cache system was added

3. **Manual deletion** of `temp_downloads/` folder

### **How to Prevent:**

1. **Check config.yaml:**
   ```yaml
   download:
     keep_files: true  # ✅ MUST be true
   ```

2. **Verify in logs:**
   ```
   ✅ KEEPING downloaded files for cache/resume
      📁 Location: /path/to/temp_downloads
      📹 Videos: 150 files
      🎵 Audio: 150 files
   ```

3. **Look for warning signs:**
   ```
   ⚠️ WARNING: DELETING ALL DOWNLOADED FILES!
   ```
   If you see this, STOP and fix config!

---

## 📊 **Understanding Cache Statistics**

After each run, you'll see:

```
============================================================
📊 CACHE STATISTICS:
   ✅ Cache Hits:       150  ← Files reused (instant)
   ⬇️  Cache Misses:     50  ← Files downloaded (slow)
   ⚠️  Corrupted Files:  2   ← Auto-fixed
   📈 Cache Hit Rate:   75.0%
   🎯 Total Requests:   200
============================================================
```

**What this means:**
- **Cache Hits:** Files found and reused (no download needed)
- **Cache Misses:** Files downloaded (took time)
- **Corrupted Files:** Bad files auto-deleted and re-downloaded
- **Hit Rate:** Percentage of files reused (higher = faster)

---

## 🔍 **Log Messages Explained**

### **✅ Cache Hit (Good!)**
```
🔍 Cache check for abc123:
   Video: abc123.mp4 - ✓ EXISTS
   Audio: abc123.mp3 - ✓ EXISTS
✅ CACHE HIT! Using cached files
   📂 Video: abc123.mp4 (15.23 MB)
   🎵 Audio: abc123.mp3 (3.45 MB)
```
**Meaning:** File found, reused instantly, no download needed

### **⬇️ Cache Miss (Need Download)**
```
🔍 Cache check for xyz789:
   Video: xyz789.mp4 - ✗ MISSING
⬇️  CACHE MISS - Downloading xyz789...
```
**Meaning:** File not found, downloading now

### **⚠️ Corrupted File (Auto-Fixed)**
```
⚠️  Cached video file is corrupted, will re-download
⬇️  CACHE MISS - Downloading abc123...
```
**Meaning:** File exists but invalid, auto-deleting and re-downloading

### **✅ Files Kept (Safe)**
```
✅ KEEPING downloaded files for cache/resume
   📁 Location: /path/to/temp_downloads
   📊 Total: 300 files cached
   💡 Tip: These files will be reused on next run (faster!)
```
**Meaning:** Files safely stored, will speed up next run

### **⚠️ Files Being Deleted (WARNING!)**
```
============================================================
⚠️  WARNING: DELETING ALL DOWNLOADED FILES!
   📁 Location: /path/to/temp_downloads
   📹 Videos: 150 files
   🎵 Audio: 150 files
   📊 Total: 300 files
   This action CANNOT be undone!
============================================================
```
**Meaning:** All files being deleted! Change config if this is not intended!

---

## 🎯 **Common Scenarios**

### **Scenario 1: First Run**
```
Run 1: 100 videos
Result: 100 cache misses (download all)
Time: 50 minutes
Files: Saved to temp_downloads/
```

### **Scenario 2: Re-run Same Data**
```
Run 2: Same 100 videos
Result: 100 cache hits (reuse all)
Time: 1 minute (50x faster!)
Files: Still in temp_downloads/
```

### **Scenario 3: Partial Re-run**
```
Run 3: 200 videos (100 old + 100 new)
Result: 100 cache hits + 100 cache misses
Time: 26 minutes (50% faster)
Files: Now 200 files in temp_downloads/
```

### **Scenario 4: Error Recovery**
```
Run 1: Processing 100 videos, error at video 50
Result: 50 files downloaded, then crash
Files: 50 files saved in temp_downloads/

Run 2: Restart processing
Result: 50 cache hits + 50 new downloads
Time: 50% saved, resume from where it stopped!
```

---

## 🛠️ **Manual File Management**

### **To Check Cached Files:**
```bash
# Windows
dir temp_downloads\videos
dir temp_downloads\audios

# Linux/Mac
ls -lh temp_downloads/videos
ls -lh temp_downloads/audios
```

### **To Manually Clean Up (If Needed):**

**Option 1: Temporary config change**
```yaml
# config.yaml
download:
  keep_files: false  # ⚠️ WARNING: Deletes all!
```
Run once, then change back to `true`

**Option 2: Manual deletion**
```bash
# Delete entire cache
rm -rf temp_downloads/

# Or keep structure, delete files only
rm temp_downloads/videos/*.mp4
rm temp_downloads/audios/*.mp3
```

---

## 📈 **Performance Comparison**

### **Without Cache (keep_files: false)**
```
Run 1: 100 videos × 30s = 50 minutes
Run 2: 100 videos × 30s = 50 minutes  ← No improvement
Run 3: 100 videos × 30s = 50 minutes  ← Wasted time!
```

### **With Cache (keep_files: true)**
```
Run 1: 100 videos × 30s = 50 minutes
Run 2: 100 videos × 0s  = 1 minute   ← 98% faster!
Run 3: 100 videos × 0s  = 1 minute   ← Consistent speed!
```

---

## ✅ **Best Practices**

1. **ALWAYS keep `keep_files: true`** unless disk space is critical
2. **Monitor cache hit rate** - aim for >70% on re-runs
3. **Let system handle corrupted files** - they auto-delete and re-download
4. **Don't manually delete temp_downloads/** during processing
5. **Check logs** to confirm files are being kept
6. **Periodically clean up** old files if disk space is low

---

## 🆘 **Troubleshooting**

### **Problem: Files keep getting deleted**

**Solution:**
```yaml
# Check config.yaml
download:
  keep_files: true  # ✅ Must be true!
```

### **Problem: Cache hits but files are corrupted**

**Solution:**
System auto-detects and fixes. Check logs for:
```
⚠️  Cached video file is corrupted, will re-download
```
This is normal and automatic.

### **Problem: Disk space running low**

**Solution:**
```yaml
# Temporarily disable cache
download:
  keep_files: false  # Clean up old files
```
Run once, then set back to `true`

### **Problem: Want to force re-download all files**

**Solution:**
```bash
# Delete cache folder
rm -rf temp_downloads/

# Next run will download everything fresh
```

---

## 📝 **Summary**

**Key Points:**
- ✅ Files kept by default (`keep_files: true`)
- ⚡ Cache = 75%+ faster re-runs
- 🛡️ Safe - no accidental deletion
- 🔧 Auto-fixes corrupted files
- 📊 Detailed statistics logged

**Remember:**
> **Keeping files = Faster, Safer, Better!**

---

**Need Help?** Check logs for detailed information about cache behavior.

**Last Updated:** 2024-11-26
