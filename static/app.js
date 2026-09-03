// PitchLab AI Frontend Application Controller

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // 2. DOM Elements
    const video = document.getElementById('pitchVideo');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const stepBackBtn = document.getElementById('stepBackBtn');
    const stepForwardBtn = document.getElementById('stepForwardBtn');
    const speedButtons = document.querySelectorAll('.speed-btn');
    const downloadBtn = document.getElementById('downloadBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const samplePitchBtn = document.getElementById('samplePitchBtn');
    const videoUploadInput = document.getElementById('videoUploadInput');
    const dropZone = document.getElementById('dropZone');
    const distancePresetSelect = document.getElementById('distancePresetSelect');
    const customDistanceRow = document.getElementById('customDistanceRow');
    const customDistanceInput = document.getElementById('customDistanceInput');

    // Telemetry Elements
    const pitchNumberBadge = document.getElementById('pitchNumberBadge');
    const pitchTagBadge = document.getElementById('pitchTagBadge');
    const strikeCallBadge = document.getElementById('strikeCallBadge');
    const velocityVal = document.getElementById('velocityVal');
    const vertBreakVal = document.getElementById('vertBreakVal');
    const horzBreakVal = document.getElementById('horzBreakVal');
    const flightTimeVal = document.getElementById('flightTimeVal');

    const sideCallBadge = document.getElementById('sideCallBadge');
    const sideVelocityMph = document.getElementById('sideVelocityMph');
    const sideVelocityKmh = document.getElementById('sideVelocityKmh');
    const sideFlightTime = document.getElementById('sideFlightTime');
    const sideVert = document.getElementById('sideVert');
    const sideHorz = document.getElementById('sideHorz');
    const sidePitchType = document.getElementById('sidePitchType');

    // Ball, Perspective & Graphic Controls
    const ballTypeSelect = document.getElementById('ballTypeSelect');
    const perspectiveSelect = document.getElementById('perspectiveSelect');
    const graphicStyleSelect = document.getElementById('graphicStyleSelect');

    // Strike Zone Controls & On-Screen Elements
    const toggleZoneEditorBtn = document.getElementById('toggleZoneEditorBtn');
    const zoneEditorToggleText = document.getElementById('zoneEditorToggleText');
    const presetBroadcastBtn = document.getElementById('presetBroadcastBtn');
    const presetBowlerBtn = document.getElementById('presetBowlerBtn');
    const presetMobileBtn = document.getElementById('presetMobileBtn');
    const applyZoneBtn = document.getElementById('applyZoneBtn');
    const interactiveZoneBox = document.getElementById('interactiveZoneBox');
    const onScreenCallTag = document.getElementById('onScreenCallTag');
    const onScreenApplyBtn = document.getElementById('onScreenApplyBtn');
    const onScreenCloseBtn = document.getElementById('onScreenCloseBtn');

    let currentPitchData = null;
    let isZoneEditorOpen = false;

    // Active Strike Zone Geometry in native video pixels
    let strikeZone = {
        cx: 1071,
        cy: 437,
        w: 120,
        h: 130
    };

    // 3. Play / Pause Controls
    playPauseBtn.addEventListener('click', () => {
        if (video.paused || video.ended) {
            video.play();
            updatePlayIcon(true);
        } else {
            video.pause();
            updatePlayIcon(false);
        }
    });

    video.addEventListener('play', () => updatePlayIcon(true));
    video.addEventListener('pause', () => updatePlayIcon(false));

    function updatePlayIcon(isPlaying) {
        playPauseBtn.innerHTML = isPlaying 
            ? '<i data-lucide="pause" class="w-5 h-5 fill-current"></i>' 
            : '<i data-lucide="play" class="w-5 h-5 fill-current"></i>';
        if (window.lucide) window.lucide.createIcons();
    }

    // 4. Frame Stepping (assuming 60 FPS standard: ~0.0166s per frame)
    const FRAME_DURATION = 1.0 / 60.0;

    stepBackBtn.addEventListener('click', () => {
        video.pause();
        video.currentTime = Math.max(0, video.currentTime - FRAME_DURATION);
    });

    stepForwardBtn.addEventListener('click', () => {
        video.pause();
        video.currentTime = Math.min(video.duration, video.currentTime + FRAME_DURATION);
    });

    // 5. Playback Speed Controls
    speedButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            speedButtons.forEach(b => {
                b.classList.remove('bg-pitchgold', 'text-black', 'shadow');
                b.classList.add('text-gray-400');
            });
            btn.classList.add('bg-pitchgold', 'text-black', 'shadow');
            btn.classList.remove('text-gray-400');
            const rate = parseFloat(btn.getAttribute('data-speed'));
            video.playbackRate = rate;
        });
    });

    // 6. Distance preset selection
    distancePresetSelect.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
            customDistanceRow.classList.remove('hidden');
        } else {
            customDistanceRow.classList.add('hidden');
        }
    });

    function getSelectedDistance() {
        if (distancePresetSelect.value === 'custom') {
            return parseFloat(customDistanceInput.value) || 60.5;
        }
        return parseFloat(distancePresetSelect.value) || 60.5;
    }

    // 7. Coordinate Mapping for On-Video Interactive Zone Box
    function getVideoRenderedGeometry() {
        const container = video.parentElement.getBoundingClientRect();
        const vidW = currentPitchData?.video_resolution?.width || (video.videoWidth || 1920);
        const vidH = currentPitchData?.video_resolution?.height || (video.videoHeight || 1080);
        const videoRatio = vidW / vidH;
        const containerRatio = container.width / container.height;

        let renderW, renderH, offsetX, offsetY;
        if (containerRatio > videoRatio) {
            renderH = container.height;
            renderW = renderH * videoRatio;
            offsetX = (container.width - renderW) / 2;
            offsetY = 0;
        } else {
            renderW = container.width;
            renderH = renderW / videoRatio;
            offsetX = 0;
            offsetY = (container.height - renderH) / 2;
        }
        return { renderW, renderH, offsetX, offsetY, vidW, vidH };
    }

    function syncInteractiveBox() {
        if (!interactiveZoneBox || interactiveZoneBox.classList.contains('hidden')) return;
        const geom = getVideoRenderedGeometry();
        const screenX = geom.offsetX + (strikeZone.cx / geom.vidW) * geom.renderW;
        const screenY = geom.offsetY + (strikeZone.cy / geom.vidH) * geom.renderH;
        const screenW = (strikeZone.w / geom.vidW) * geom.renderW;
        const screenH = (strikeZone.h / geom.vidH) * geom.renderH;

        interactiveZoneBox.style.left = `${screenX}px`;
        interactiveZoneBox.style.top = `${screenY}px`;
        interactiveZoneBox.style.width = `${Math.max(30, screenW)}px`;
        interactiveZoneBox.style.height = `${Math.max(30, screenH)}px`;

        checkLiveStrikeCall();
    }

    function checkLiveStrikeCall() {
        if (!currentPitchData?.plate_crossing) return;
        const x_min = strikeZone.cx - (strikeZone.w / 2.0);
        const x_max = strikeZone.cx + (strikeZone.w / 2.0);
        const y_min = strikeZone.cy - (strikeZone.h / 2.0);
        const y_max = strikeZone.cy + (strikeZone.h / 2.0);

        const px = currentPitchData.plate_crossing.x;
        const py = currentPitchData.plate_crossing.y;
        const ballR = 14.0;

        const isStrike = (px >= x_min - ballR) && (px <= x_max + ballR) &&
                         (py >= y_min - ballR) && (py <= y_max + ballR);

        updateCallBadges(isStrike);
        if (onScreenCallTag) {
            onScreenCallTag.textContent = isStrike ? 'STRIKE' : 'BALL';
            if (isStrike) {
                onScreenCallTag.className = 'text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-pitchgreen/20 text-pitchgreen border border-pitchgreen/50 shadow-sm shadow-pitchgreen/30';
            } else {
                onScreenCallTag.className = 'text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-pitchred/20 text-pitchred border border-pitchred/50 shadow-sm shadow-pitchred/30';
            }
        }
    }

    function updateCallBadges(isStrike) {
        const text = isStrike ? 'STRIKE' : 'BALL';
        strikeCallBadge.textContent = text;
        sideCallBadge.textContent = text;

        if (isStrike) {
            strikeCallBadge.className = 'px-3 py-1 rounded-md text-xs font-black tracking-wider uppercase bg-pitchgreen/20 text-pitchgreen border border-pitchgreen/50 shadow-sm shadow-pitchgreen/30';
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-1 rounded bg-pitchgreen/20 text-pitchgreen border border-pitchgreen/40';
        } else {
            strikeCallBadge.className = 'px-3 py-1 rounded-md text-xs font-black tracking-wider uppercase bg-pitchred/20 text-pitchred border border-pitchred/50 shadow-sm shadow-pitchred/30';
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-1 rounded bg-pitchred/20 text-pitchred border border-pitchred/40';
        }
    }

    // Toggle on-screen zone editor
    function setZoneEditorOpen(open) {
        isZoneEditorOpen = open;
        if (isZoneEditorOpen) {
            interactiveZoneBox.classList.remove('hidden');
            zoneEditorToggleText.textContent = 'Hide Box';
            toggleZoneEditorBtn.classList.add('bg-pitchgold', 'text-black');
            toggleZoneEditorBtn.classList.remove('bg-gray-800', 'text-pitchgold');
            syncInteractiveBox();
        } else {
            interactiveZoneBox.classList.add('hidden');
            zoneEditorToggleText.textContent = 'Position On Screen';
            toggleZoneEditorBtn.classList.remove('bg-pitchgold', 'text-black');
            toggleZoneEditorBtn.classList.add('bg-gray-800', 'text-pitchgold');
        }
    }

    const videoZoneToggleBtn = document.getElementById('videoZoneToggleBtn');

    toggleZoneEditorBtn.addEventListener('click', () => {
        setZoneEditorOpen(!isZoneEditorOpen);
    });

    videoZoneToggleBtn?.addEventListener('click', () => {
        setZoneEditorOpen(!isZoneEditorOpen);
    });

    onScreenCloseBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        setZoneEditorOpen(false);
    });

    // Preset buttons
    presetBroadcastBtn?.addEventListener('click', () => {
        const vidW = currentPitchData?.video_resolution?.width || 1920;
        const vidH = currentPitchData?.video_resolution?.height || 1080;
        strikeZone = {
            cx: Math.round(vidW * 0.558),
            cy: Math.round(vidH * 0.405),
            w: Math.round(vidW * 0.062),
            h: Math.round(vidH * 0.116),
        };
        setZoneEditorOpen(true);
        syncInteractiveBox();
    });

    presetBowlerBtn?.addEventListener('click', () => {
        const vidW = currentPitchData?.video_resolution?.width || 478;
        const vidH = currentPitchData?.video_resolution?.height || 850;
        strikeZone = {
            cx: Math.round(vidW * 0.52),
            cy: Math.round(vidH * 0.42),
            w: Math.round(vidW * 0.18),
            h: Math.round(vidH * 0.20),
        };
        setZoneEditorOpen(true);
        syncInteractiveBox();
    });

    presetMobileBtn?.addEventListener('click', () => {
        const vidW = currentPitchData?.video_resolution?.width || 384;
        const vidH = currentPitchData?.video_resolution?.height || 848;
        strikeZone = {
            cx: Math.round(vidW * 0.50),
            cy: Math.round(vidH * 0.68),
            w: Math.round(vidW * 0.24),
            h: Math.round(vidH * 0.17),
        };
        setZoneEditorOpen(true);
        syncInteractiveBox();
    });

    // 8. Pure Direct On-Screen Drag and 4-Corner Resizing
    let activeAction = null; // 'drag', 'nw', 'ne', 'sw', 'se'
    let startMouseX = 0;
    let startMouseY = 0;
    let startZone = { cx: 0, cy: 0, w: 0, h: 0 };

    interactiveZoneBox.addEventListener('mousedown', (e) => {
        if (e.target.closest('#onScreenApplyBtn') || e.target.closest('#onScreenCloseBtn')) {
            return;
        }
        const handle = e.target.getAttribute('data-handle');
        if (handle) {
            activeAction = handle;
        } else {
            activeAction = 'drag';
        }
        startMouseX = e.clientX;
        startMouseY = e.clientY;
        startZone = { ...strikeZone };
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!activeAction) return;
        const geom = getVideoRenderedGeometry();
        const deltaVidX = (e.clientX - startMouseX) * (geom.vidW / geom.renderW);
        const deltaVidY = (e.clientY - startMouseY) * (geom.vidH / geom.renderH);

        if (activeAction === 'drag') {
            strikeZone.cx = Math.max(10, Math.min(geom.vidW - 10, startZone.cx + deltaVidX));
            strikeZone.cy = Math.max(10, Math.min(geom.vidH - 10, startZone.cy + deltaVidY));
        } else if (activeAction === 'se') {
            strikeZone.w = Math.max(25, Math.min(geom.vidW, startZone.w + deltaVidX * 2));
            strikeZone.h = Math.max(25, Math.min(geom.vidH, startZone.h + deltaVidY * 2));
        } else if (activeAction === 'sw') {
            strikeZone.w = Math.max(25, Math.min(geom.vidW, startZone.w - deltaVidX * 2));
            strikeZone.h = Math.max(25, Math.min(geom.vidH, startZone.h + deltaVidY * 2));
        } else if (activeAction === 'ne') {
            strikeZone.w = Math.max(25, Math.min(geom.vidW, startZone.w + deltaVidX * 2));
            strikeZone.h = Math.max(25, Math.min(geom.vidH, startZone.h - deltaVidY * 2));
        } else if (activeAction === 'nw') {
            strikeZone.w = Math.max(25, Math.min(geom.vidW, startZone.w - deltaVidX * 2));
            strikeZone.h = Math.max(25, Math.min(geom.vidH, startZone.h - deltaVidY * 2));
        }

        syncInteractiveBox();
    });

    window.addEventListener('mouseup', () => {
        activeAction = null;
    });

    window.addEventListener('resize', () => {
        syncInteractiveBox();
    });

    video.addEventListener('loadedmetadata', () => {
        syncInteractiveBox();
    });

    // 9. Update UI with Telemetry Results
    function updateTelemetry(data) {
        currentPitchData = data;

        // Call Badges
        updateCallBadges(data.is_strike);

        // Velocity
        velocityVal.textContent = data.velocity_mph.toFixed(1);
        sideVelocityMph.textContent = data.velocity_mph.toFixed(1);
        sideVelocityKmh.textContent = (data.velocity_kmh || (data.velocity_mph * 1.60934)).toFixed(1);

        // Break & Flight
        vertBreakVal.textContent = (data.vert_break_in >= 0 ? '+' : '') + data.vert_break_in.toFixed(1);
        horzBreakVal.textContent = (data.horz_break_in >= 0 ? '+' : '') + data.horz_break_in.toFixed(1);
        sideVert.textContent = `V: ${(data.vert_break_in >= 0 ? '+' : '')}${data.vert_break_in.toFixed(1)}"`;
        sideHorz.textContent = `H: ${(data.horz_break_in >= 0 ? '+' : '')}${data.horz_break_in.toFixed(1)}"`;

        flightTimeVal.textContent = Math.round(data.flight_time_ms);
        sideFlightTime.textContent = `${Math.round(data.flight_time_ms)} ms`;

        // Dismiss empty state and reveal HUD card
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.classList.add('hidden');
        const hudCard = document.getElementById('hudCard');
        if (hudCard) hudCard.classList.remove('hidden');

        // Tags
        const tag = data.pitch_tag || 'Fastball';
        pitchTagBadge.textContent = tag;
        sidePitchType.textContent = tag;
        pitchNumberBadge.textContent = `Pitch #${data.pitch_number || 1}`;

        // Strike Zone synchronization
        if (data.strike_zone) {
            const cx = (data.strike_zone.x_min + data.strike_zone.x_max) / 2.0;
            const cy = (data.strike_zone.y_min + data.strike_zone.y_max) / 2.0;
            const w = data.strike_zone.x_max - data.strike_zone.x_min;
            const h = data.strike_zone.y_max - data.strike_zone.y_min;
            strikeZone = { cx, cy, w, h };
            syncInteractiveBox();
        }

        if (data.ball_type && ballTypeSelect) {
            ballTypeSelect.value = data.ball_type;
        }
        if (data.perspective && perspectiveSelect) {
            perspectiveSelect.value = data.perspective;
        }
        if (data.graphic_style) {
            graphicStyleSelect.value = data.graphic_style;
        }

        // Switch video source to rendered result
        if (data.video_url) {
            const cleanUrl = data.video_url + '?t=' + Date.now();
            video.src = cleanUrl;
            downloadBtn.href = data.video_url;
            video.load();
            video.play().catch(() => {});
        }
    }

    // 10. Fast Re-Render on Strike Zone / Theme Change
    async function applyStrikeZoneChanges() {
        if (!currentPitchData || !currentPitchData.trajectory) {
            alert('Please load or upload a pitch video first.');
            return;
        }

        loadingOverlay.classList.remove('hidden');

        const style = graphicStyleSelect.value;
        const ballType = ballTypeSelect?.value || 'auto';
        const perspective = perspectiveSelect?.value || 'auto';

        const payload = {
            video_id: currentPitchData.video_id || 'sample',
            trajectory: currentPitchData.trajectory,
            distance_ft: getSelectedDistance(),
            custom_strike_zone: {
                x_min: strikeZone.cx - (strikeZone.w / 2.0),
                y_min: strikeZone.cy - (strikeZone.h / 2.0),
                x_max: strikeZone.cx + (strikeZone.w / 2.0),
                y_max: strikeZone.cy + (strikeZone.h / 2.0),
            },
            graphic_style: style,
            ball_type: ballType,
            perspective: perspective,
            pitch_number: currentPitchData.pitch_number || 1
        };

        try {
            const res = await fetch('/api/rerender', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Re-render failed');
            }

            const data = await res.json();
            updateTelemetry(data);
        } catch (err) {
            alert('Re-render error: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    applyZoneBtn?.addEventListener('click', applyStrikeZoneChanges);
    onScreenApplyBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        applyStrikeZoneChanges();
    });

    // 11. Upload Video Workflow
    async function uploadAndProcessVideo(file) {
        loadingOverlay.classList.remove('hidden');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('distance_ft', getSelectedDistance());
        formData.append('pitch_number', 1);
        formData.append('graphic_style', graphicStyleSelect.value);
        formData.append('ball_type', ballTypeSelect?.value || 'auto');
        formData.append('perspective', perspectiveSelect?.value || 'auto');

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Video processing failed');
            }

            const data = await response.json();
            updateTelemetry(data);
        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    videoUploadInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            uploadAndProcessVideo(e.target.files[0]);
        }
    });

    // 12. Drag and Drop
    dropZone.addEventListener('click', () => videoUploadInput.click());
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('border-pitchgold', 'bg-pitchgold/5');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-pitchgold', 'bg-pitchgold/5');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            uploadAndProcessVideo(e.dataTransfer.files[0]);
        }
    });

    // 13. Sample Pitch Demo Button
    samplePitchBtn.addEventListener('click', async () => {
        loadingOverlay.classList.remove('hidden');
        try {
            const response = await fetch('/api/sample');
            if (!response.ok) throw new Error('Failed to load sample pitch');
            const data = await response.json();
            updateTelemetry(data);
        } catch (err) {
            console.warn("Falling back to pre-rendered video URL", err);
            video.src = '/api/video/pitchlab_result.mp4';
            video.load();
            video.play().catch(() => {});
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });
});
