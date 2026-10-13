// ==========================================================================
// VeloPath AI Studio - Frontend Application Controller
// ==========================================================================

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
    const videoScrubber = document.getElementById('videoScrubber');
    const currentTimeDisplay = document.getElementById('currentTimeDisplay');
    const durationDisplay = document.getElementById('durationDisplay');
    const speedButtons = document.querySelectorAll('.speed-btn');
    const downloadBtn = document.getElementById('downloadBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingStatusText = document.getElementById('loadingStatusText');
    const samplePitchBtn = document.getElementById('samplePitchBtn');
    const videoUploadInput = document.getElementById('videoUploadInput');
    const videoDropZone = document.getElementById('videoDropZone');
    const emptyState = document.getElementById('emptyState');
    const toggleHudBtn = document.getElementById('toggleHudBtn');

    // Telemetry Elements
    const heroVelocityVal = document.getElementById('heroVelocityVal');
    const heroVelocityKmh = document.getElementById('heroVelocityKmh');
    const plateVelocityVal = document.getElementById('plateVelocityVal');
    const plateVelocityKmh = document.getElementById('plateVelocityKmh');
    const dragLossPct = document.getElementById('dragLossPct');
    const proofFramesCount = document.getElementById('proofFramesCount');
    const proofTimeStr = document.getElementById('proofTimeStr');
    const proofDistStr = document.getElementById('proofDistStr');
    const proofFormulaStr = document.getElementById('proofFormulaStr');
    const flightTimeVal = document.getElementById('flightTimeVal');
    const vertBreakVal = document.getElementById('vertBreakVal');
    const horzBreakVal = document.getElementById('horzBreakVal');
    const sidePitchType = document.getElementById('sidePitchType');
    const sideCallBadge = document.getElementById('sideCallBadge');

    // On-Video Overlays
    const videoOverlayPill = document.getElementById('videoOverlayPill');
    const overlayPitchNum = document.getElementById('overlayPitchNum');
    const overlayPitchTag = document.getElementById('overlayPitchTag');
    const overlayVelocityVal = document.getElementById('overlayVelocityVal');
    const videoOverlayCall = document.getElementById('videoOverlayCall');
    const overlayCallText = document.getElementById('overlayCallText');

    // Strike Zone Elements
    const interactiveZoneBox = document.getElementById('interactiveZoneBox');
    const zoneCalibrationDock = document.getElementById('zoneCalibrationDock');
    const dockApplyBtn = document.getElementById('dockApplyBtn');
    const dockCancelBtn = document.getElementById('dockCancelBtn');
    const dockTapPlateBtn = document.getElementById('dockTapPlateBtn');
    const dockBatterHeight = document.getElementById('dockBatterHeight');
    const videoZoneToggleBtn = document.getElementById('videoZoneToggleBtn');
    const videoStage = document.getElementById('videoStage');
    const zoneZoomToggleBtn = document.getElementById('zoneZoomToggleBtn');
    const zoomControlDock = document.getElementById('zoomControlDock');
    const zoomLevelDisplay = document.getElementById('zoomLevelDisplay');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const calibrateZoneSidebarBtn = document.getElementById('calibrateZoneSidebarBtn');
    const applyZoneChangesBtn = document.getElementById('applyZoneChangesBtn');
    const zoneWVal = document.getElementById('zoneWVal');
    const zoneHVal = document.getElementById('zoneHVal');
    const zoneXVal = document.getElementById('zoneXVal');
    const zoneYVal = document.getElementById('zoneYVal');
    const sideZoneCallStatus = document.getElementById('sideZoneCallStatus');
    const perspectiveButtons = document.querySelectorAll('.perspective-btn');

    // Settings & Selectors
    const distancePresetSelect = document.getElementById('distancePresetSelect');
    const customDistanceRow = document.getElementById('customDistanceRow');
    const customDistanceInput = document.getElementById('customDistanceInput');
    const ballTypeSelect = document.getElementById('ballTypeSelect');
    const themeChips = document.querySelectorAll('.theme-chip');
    const cleanVideoCheckbox = document.getElementById('cleanVideoCheckbox');
    const trimPitchCheckbox = document.getElementById('trimPitchCheckbox');

    // Tracking Mode Elements
    const modeBaseballBtn = document.getElementById('modeBaseballBtn');
    const modeNormalBtn = document.getElementById('modeNormalBtn');
    const modeStatusPill = document.getElementById('modeStatusPill');
    const modeDescriptionText = document.getElementById('modeDescriptionText');
    const normalModeNotice = document.getElementById('normalModeNotice');

    // Modals
    const helpModal = document.getElementById('helpModal');
    const helpModalBtn = document.getElementById('helpModalBtn');
    const closeHelpModalBtn = document.getElementById('closeHelpModalBtn');

    // State Variables
    let currentPitchData = null;
    let isZoneCalibrating = false;
    let isHudVisible = true;
    let activeGraphicStyle = 'statcast_cyan';
    let activePerspective = 'auto';
    let activeTrackingMode = 'baseball'; // 'baseball' or 'normal'

    // Active Strike Zone Geometry in native video pixels
    let strikeZone = {
        cx: 540,
        cy: 960,
        w: 180,
        h: 210
    };

    function setTrackingMode(mode) {
        activeTrackingMode = mode;
        if (mode === 'normal') {
            if (modeNormalBtn) modeNormalBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-bold bg-pitchcyan text-black shadow-sm transition flex items-center gap-1.5';
            if (modeBaseballBtn) modeBaseballBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
            if (modeStatusPill) {
                modeStatusPill.textContent = '🎯 Normal Video Mode';
                modeStatusPill.className = 'text-[10px] font-semibold text-pitchcyan px-2 py-0.5 rounded-full bg-pitchcyan/10 border border-pitchcyan/20';
            }
            if (modeDescriptionText) {
                modeDescriptionText.textContent = 'Tracks full-frame ball throws, high arcs, tosses, and catches in any direction without baseball constraints.';
            }
            if (normalModeNotice) normalModeNotice.classList.remove('hidden');
            if (interactiveZoneBox) interactiveZoneBox.classList.add('hidden');
        } else {
            if (modeBaseballBtn) modeBaseballBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-bold bg-pitchcyan text-black shadow-sm transition flex items-center gap-1.5';
            if (modeNormalBtn) modeNormalBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
            if (modeStatusPill) {
                modeStatusPill.textContent = '⚾ Baseball ABS Mode';
                modeStatusPill.className = 'text-[10px] font-semibold text-pitchcyan px-2 py-0.5 rounded-full bg-pitchcyan/10 border border-pitchcyan/20';
            }
            if (modeDescriptionText) {
                modeDescriptionText.textContent = 'Pitch tunnel gating, 60.5ft ABS strike zone, and Statcast 3D streamline.';
            }
            if (normalModeNotice) normalModeNotice.classList.add('hidden');
            if (interactiveZoneBox && isZoneCalibrating) interactiveZoneBox.classList.remove('hidden');
        }
        if (window.lucide) window.lucide.createIcons();
    }

    if (modeBaseballBtn) modeBaseballBtn.addEventListener('click', () => setTrackingMode('baseball'));
    if (modeNormalBtn) modeNormalBtn.addEventListener('click', () => setTrackingMode('normal'));

    // 3. Check System Hardware Acceleration
    async function checkHardwareHealth() {
        try {
            const res = await fetch('/api/health');
            if (res.ok) {
                const data = await res.json();
                const hwEl = document.getElementById('hardwareText');
                if (hwEl) {
                    hwEl.textContent = 'Hardware Accelerated';
                }
            }
        } catch (e) {}
    }
    checkHardwareHealth();

    // 4. Play / Pause & Scrubber Synchronization
    playPauseBtn.addEventListener('click', () => {
        if (video.paused || video.ended) {
            video.play();
        } else {
            video.pause();
        }
    });

    video.addEventListener('play', () => updatePlayState(true));
    video.addEventListener('pause', () => updatePlayState(false));

    function updatePlayState(isPlaying) {
        playPauseBtn.innerHTML = isPlaying 
            ? '<i data-lucide="pause" class="w-5 h-5 fill-current"></i>' 
            : '<i data-lucide="play" class="w-5 h-5 fill-current"></i>';
        if (window.lucide) window.lucide.createIcons();
    }

    video.addEventListener('timeupdate', () => {
        if (!video.duration) return;
        const pct = (video.currentTime / video.duration) * 100;
        videoScrubber.value = pct;
        currentTimeDisplay.textContent = `${video.currentTime.toFixed(2)}s`;
    });

    video.addEventListener('loadedmetadata', () => {
        durationDisplay.textContent = `${video.duration.toFixed(2)}s`;
        syncInteractiveBox();
    });

    videoScrubber.addEventListener('input', () => {
        if (!video.duration) return;
        video.currentTime = (videoScrubber.value / 100) * video.duration;
    });

    // 5. Frame Stepping (60 FPS standard ~0.0166s per frame)
    const FRAME_STEP = 1.0 / 60.0;

    stepBackBtn.addEventListener('click', () => {
        video.pause();
        video.currentTime = Math.max(0, video.currentTime - FRAME_STEP);
    });

    stepForwardBtn.addEventListener('click', () => {
        video.pause();
        video.currentTime = Math.min(video.duration || 10, video.currentTime + FRAME_STEP);
    });

    // 6. Playback Speed Presets
    speedButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            speedButtons.forEach(b => {
                b.classList.remove('bg-pitchcyan', 'text-black', 'font-bold', 'shadow-sm');
                b.classList.add('text-slate-400', 'font-medium');
            });
            btn.classList.add('bg-pitchcyan', 'text-black', 'font-bold', 'shadow-sm');
            btn.classList.remove('text-slate-400', 'font-medium');
            video.playbackRate = parseFloat(btn.getAttribute('data-speed')) || 1.0;
        });
    });

    // 7. Mound Distance Handling
    distancePresetSelect.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
            customDistanceRow.classList.remove('hidden');
        } else {
            customDistanceRow.classList.add('hidden');
            if (currentPitchData) {
                applyStrikeZoneChanges();
            }
        }
    });

    customDistanceInput.addEventListener('change', () => {
        if (currentPitchData) {
            applyStrikeZoneChanges();
        }
    });

    function getSelectedDistance() {
        if (distancePresetSelect.value === 'custom') {
            return parseFloat(customDistanceInput.value) || 60.5;
        }
        return parseFloat(distancePresetSelect.value) || 60.5;
    }

    // 8. Streamline Theme Selection Chips
    themeChips.forEach(chip => {
        chip.addEventListener('click', () => {
            themeChips.forEach(c => {
                c.classList.remove('border-pitchcyan/60', 'text-white', 'font-bold');
                c.classList.add('border-white/10', 'text-slate-400', 'font-semibold');
            });
            chip.classList.add('border-pitchcyan/60', 'text-white', 'font-bold');
            chip.classList.remove('border-white/10', 'text-slate-400', 'font-semibold');
            activeGraphicStyle = chip.getAttribute('data-theme');
            if (currentPitchData) {
                applyStrikeZoneChanges();
            }
        });
    });

    // 9. Perspective Presets
    perspectiveButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            perspectiveButtons.forEach(b => {
                b.classList.remove('bg-pitchcyan', 'text-black', 'font-bold');
                b.classList.add('text-slate-400', 'font-semibold');
            });
            btn.classList.add('bg-pitchcyan', 'text-black', 'font-bold');
            btn.classList.remove('text-slate-400', 'font-semibold');

            activePerspective = btn.getAttribute('data-perspective');
            applyPerspectivePreset(activePerspective);
        });
    });

    function applyPerspectivePreset(persp) {
        const vidW = currentPitchData?.video_resolution?.width || 1920;
        const vidH = currentPitchData?.video_resolution?.height || 1080;
        const isPortrait = vidH > vidW;

        let effectivePersp = persp;
        if (persp === 'auto') {
            effectivePersp = currentPitchData?.perspective || (isPortrait ? 'behind_pitcher' : 'behind_plate');
        }

        if (effectivePersp === 'broadcast') {
            strikeZone = {
                cx: Math.round(vidW * 0.558),
                cy: Math.round(vidH * 0.405),
                w: Math.round(vidW * 0.062),
                h: Math.round(vidH * 0.116),
            };
        } else if (effectivePersp === 'behind_plate' || effectivePersp === 'behind_catcher') {
            strikeZone = {
                cx: Math.round(vidW * 0.68),
                cy: Math.round(vidH * 0.58),
                w: Math.round(vidW * 0.16),
                h: Math.round(vidH * 0.22),
            };
        } else {
            // behind_pitcher
            strikeZone = {
                cx: Math.round(vidW * 0.52),
                cy: Math.round(vidH * 0.48),
                w: Math.round(vidW * 0.16),
                h: Math.round(vidH * 0.20),
            };
        }
        setCalibrationMode(true);
        syncInteractiveBox();
    }

    function getVideoRenderedGeometry() {
        const container = videoDropZone.getBoundingClientRect();
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
        interactiveZoneBox.style.width = `${Math.max(28, screenW)}px`;
        interactiveZoneBox.style.height = `${Math.max(28, screenH)}px`;

        // Update Coordinate displays
        const pctX = Math.round((strikeZone.cx / geom.vidW) * 100);
        const pctY = Math.round((strikeZone.cy / geom.vidH) * 100);
        zoneXVal.textContent = `${pctX}%`;
        zoneYVal.textContent = `${pctY}%`;
        zoneWVal.textContent = `${Math.round(strikeZone.w)}`;
        zoneHVal.textContent = `${Math.round(strikeZone.h)}`;

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
        const ballR = 1.45 * strikeZone.w / 17.0;  // baseball radius at zone scale (zone = 17in wide)

        const isStrike = (px >= x_min - ballR) && (px <= x_max + ballR) &&
                         (py >= y_min - ballR) && (py <= y_max + ballR);

        updateCallState(isStrike);
    }

    function updateCallState(isStrike, pitchDetected = true, zoneCalibrated = true) {
        if (!pitchDetected || !zoneCalibrated) {
            const text = pitchDetected ? 'SET ZONE' : 'NO PITCH';
            sideCallBadge.textContent = text;
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-0.5 rounded-md bg-slate-500/20 text-slate-300 border border-slate-500/40';
            sideZoneCallStatus.textContent = text;
            sideZoneCallStatus.className = 'font-black text-slate-300 uppercase text-[11px]';
            if (dockCallStatus) {
                dockCallStatus.textContent = text;
                dockCallStatus.className = 'text-[10px] font-black px-2 py-0.5 rounded uppercase bg-slate-500/20 text-slate-300 border border-slate-500/30';
            }
            interactiveZoneBox.classList.remove('is-strike', 'is-ball');
            overlayCallText.textContent = text;
            overlayCallText.className = 'text-xs font-black tracking-wider uppercase px-2 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-500/40';
            return;
        }

        if (activeTrackingMode === 'normal' || currentPitchData?.mode === 'normal') {
            const text = 'TRACKED';
            sideCallBadge.textContent = text;
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-0.5 rounded-md bg-pitchcyan/20 text-pitchcyan border border-pitchcyan/40';
            sideZoneCallStatus.textContent = 'BALL TRACKED';
            sideZoneCallStatus.className = 'font-black text-pitchcyan uppercase text-[11px]';
            if (dockCallStatus) {
                dockCallStatus.textContent = 'TRACKED';
                dockCallStatus.className = 'text-[10px] font-black px-2 py-0.5 rounded uppercase bg-pitchcyan/20 text-pitchcyan border border-pitchcyan/30';
            }
            interactiveZoneBox.classList.remove('is-strike', 'is-ball');
            overlayCallText.textContent = text;
            overlayCallText.className = 'text-xs font-black tracking-wider uppercase px-2 py-0.5 rounded bg-pitchcyan/20 text-pitchcyan border border-pitchcyan/40';
            return;
        }

        const text = isStrike ? 'STRIKE' : 'BALL';
        
        // Sidebar Badge
        sideCallBadge.textContent = text;
        if (isStrike) {
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 glow-emerald';
            sideZoneCallStatus.textContent = 'STRIKE (In Zone)';
            sideZoneCallStatus.className = 'font-black text-emerald-400 uppercase text-[11px]';
            dockCallStatus.textContent = 'IN ZONE';
            dockCallStatus.className = 'text-[10px] font-black px-2 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
            interactiveZoneBox.classList.add('is-strike');
            interactiveZoneBox.classList.remove('is-ball');
        } else {
            sideCallBadge.className = 'text-xs font-black uppercase px-2.5 py-0.5 rounded-md bg-rose-500/20 text-rose-400 border border-rose-500/40 glow-red';
            sideZoneCallStatus.textContent = 'BALL (Outside Zone)';
            sideZoneCallStatus.className = 'font-black text-rose-400 uppercase text-[11px]';
            dockCallStatus.textContent = 'OUT OF ZONE';
            dockCallStatus.className = 'text-[10px] font-black px-2 py-0.5 rounded uppercase bg-rose-500/20 text-rose-400 border border-rose-500/30';
            interactiveZoneBox.classList.add('is-ball');
            interactiveZoneBox.classList.remove('is-strike');
        }

        // On-Video Overlay Call
        overlayCallText.textContent = text;
        if (isStrike) {
            overlayCallText.className = 'text-xs font-black tracking-wider uppercase px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 glow-emerald';
        } else {
            overlayCallText.className = 'text-xs font-black tracking-wider uppercase px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/40 glow-red';
        }
    }

    // 11. Calibration Mode Toggle (Non-Obtrusive)
    function setCalibrationMode(calibrating) {
        isZoneCalibrating = calibrating;
        if (isZoneCalibrating) {
            video.pause();
            interactiveZoneBox.classList.remove('hidden');
            zoneCalibrationDock.classList.remove('hidden');
            videoZoneToggleBtn.classList.add('bg-pitchcyan', 'text-black');
            videoZoneToggleBtn.classList.remove('bg-slate-800', 'text-pitchcyan');
            syncInteractiveBox();
        } else {
            interactiveZoneBox.classList.add('hidden');
            zoneCalibrationDock.classList.add('hidden');
            videoZoneToggleBtn.classList.remove('bg-pitchcyan', 'text-black');
            videoZoneToggleBtn.classList.add('bg-slate-800', 'text-pitchcyan');
        }
    }

    videoZoneToggleBtn.addEventListener('click', () => setCalibrationMode(!isZoneCalibrating));
    calibrateZoneSidebarBtn.addEventListener('click', () => setCalibrationMode(!isZoneCalibrating));
    dockCancelBtn.addEventListener('click', () => setCalibrationMode(false));

    // 12. Direct Drag & 4-Corner Resize Handling
    let activeAction = null;
    let startMouseX = 0;
    let startMouseY = 0;
    let startZone = { cx: 0, cy: 0, w: 0, h: 0 };

    interactiveZoneBox.addEventListener('mousedown', (e) => {
        const handle = e.target.getAttribute('data-handle');
        activeAction = handle || 'drag';
        startMouseX = e.clientX;
        startMouseY = e.clientY;
        startZone = { ...strikeZone };
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!activeAction) return;
        const geom = getVideoRenderedGeometry();
        const deltaVidX = ((e.clientX - startMouseX) * (geom.vidW / geom.renderW)) / (currentZoom || 1.0);
        const deltaVidY = ((e.clientY - startMouseY) * (geom.vidH / geom.renderH)) / (currentZoom || 1.0);

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

    window.addEventListener('resize', syncInteractiveBox);

    // 13. Strike Zone Zoom & Close-Inspection Engine
    let currentZoom = 1.0;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;
    let startPanX = 0;
    let startPanY = 0;

    function applyZoom(zoom, smooth = true) {
        currentZoom = Math.max(1.0, Math.min(4.5, zoom));

        if (smooth) {
            videoStage.style.transition = 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)';
        } else {
            videoStage.style.transition = 'none';
        }

        if (currentZoom <= 1.01) {
            currentZoom = 1.0;
            panX = 0;
            panY = 0;
            videoStage.style.transformOrigin = 'center center';
            videoStage.style.transform = 'scale(1) translate(0px, 0px)';
            zoomControlDock.classList.add('hidden');
            zoneZoomToggleBtn.classList.remove('bg-pitchcyan', 'text-black', 'font-bold');
            zoneZoomToggleBtn.classList.add('text-slate-300');
            videoDropZone.style.cursor = 'default';
        } else {
            // Center zoom transform origin directly on Strike Zone center
            const geom = getVideoRenderedGeometry();
            const szScreenX = geom.offsetX + (strikeZone.cx / geom.vidW) * geom.renderW;
            const szScreenY = geom.offsetY + (strikeZone.cy / geom.vidH) * geom.renderH;

            videoStage.style.transformOrigin = `${szScreenX}px ${szScreenY}px`;
            videoStage.style.transform = `scale(${currentZoom}) translate(${panX}px, ${panY}px)`;

            zoomControlDock.classList.remove('hidden');
            zoomLevelDisplay.textContent = `${currentZoom.toFixed(1)}x`;
            zoneZoomToggleBtn.classList.add('bg-pitchcyan', 'text-black', 'font-bold');
            zoneZoomToggleBtn.classList.remove('text-slate-300');
            videoDropZone.style.cursor = 'grab';
        }
    }

    function toggleZoneZoom() {
        if (currentZoom > 1.05) {
            applyZoom(1.0, true);
        } else {
            panX = 0;
            panY = 0;
            applyZoom(2.5, true);
        }
    }

    if (zoneZoomToggleBtn) zoneZoomToggleBtn.addEventListener('click', toggleZoneZoom);
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => applyZoom(currentZoom + 0.5, true));
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => applyZoom(currentZoom - 0.5, true));
    if (zoomResetBtn) zoomResetBtn.addEventListener('click', () => applyZoom(1.0, true));

    // Mouse Wheel Zoom
    videoDropZone.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.35 : -0.35;
        applyZoom(currentZoom + delta, true);
    }, { passive: false });

    // Double-click to toggle Zoom into Strike Zone
    videoDropZone.addEventListener('dblclick', (e) => {
        if (e.target.closest('button') || e.target.closest('.zone-anchor') || e.target.closest('#zoomControlDock')) return;
        toggleZoneZoom();
    });

    // Panning when zoomed in
    videoDropZone.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('zone-anchor') || e.target.closest('button') || e.target.closest('#zoomControlDock')) {
            return;
        }
        if (currentZoom > 1.0) {
            isPanning = true;
            panStartX = e.clientX;
            panStartY = e.clientY;
            startPanX = panX;
            startPanY = panY;
            videoDropZone.style.cursor = 'grabbing';
            videoStage.style.transition = 'none';
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        const dx = (e.clientX - panStartX) / currentZoom;
        const dy = (e.clientY - panStartY) / currentZoom;
        panX = startPanX + dx;
        panY = startPanY + dy;
        applyZoom(currentZoom, false);
    });

    window.addEventListener('mouseup', () => {
        if (isPanning) {
            isPanning = false;
            if (currentZoom > 1.0) {
                videoDropZone.style.cursor = 'grab';
            }
        }
    });

    // 13. HUD Visibility Toggle
    toggleHudBtn.addEventListener('click', () => {
        isHudVisible = !isHudVisible;
        if (isHudVisible) {
            videoOverlayPill.classList.remove('opacity-0');
            videoOverlayCall.classList.remove('opacity-0');
            toggleHudBtn.classList.add('text-pitchcyan');
        } else {
            videoOverlayPill.classList.add('opacity-0');
            videoOverlayCall.classList.add('opacity-0');
            toggleHudBtn.classList.remove('text-pitchcyan');
        }
    });

    // 14. Update UI with Telemetry Results
    function updateTelemetry(data) {
        currentPitchData = data;

        // Dismiss empty state
        if (emptyState) emptyState.classList.add('hidden');

        // Hero Velocity (Release & Plate with Drag)
        heroVelocityVal.textContent = data.velocity_mph.toFixed(1);
        heroVelocityKmh.textContent = (data.velocity_kmh || (data.velocity_mph * 1.60934)).toFixed(1);
        // flight time is whole frames: one frame of error moves speed by this much
        const heroVelocityPm = document.getElementById('heroVelocityPm');
        if (heroVelocityPm) {
            const lowFps = (data.fps || 30) < 60;
            heroVelocityPm.textContent = data.velocity_pm_mph ? `±${data.velocity_pm_mph.toFixed(1)}${lowFps ? ' · low fps' : ''}` : '';
            heroVelocityPm.title = lowFps ? 'Timing is counted in whole frames. Record at 60+ fps (240 fps slow-mo is best) for a tighter speed.' : 'One frame of timing error';
        }

        const plateMph = data.plate_velocity_mph || (data.velocity_mph * 0.95);
        const plateKmh = data.plate_velocity_kmh || (plateMph * 1.60934);
        if (plateVelocityVal) plateVelocityVal.textContent = plateMph.toFixed(1);
        if (plateVelocityKmh) plateVelocityKmh.textContent = plateKmh.toFixed(1);

        const dragLoss = ((data.velocity_mph - plateMph) / Math.max(1, data.velocity_mph)) * 100.0;
        if (dragLossPct) dragLossPct.textContent = `-${dragLoss.toFixed(1)}%`;
        
        // Mathematical Proof Breakdown
        const elapsedFrames = data.elapsed_frames || Math.round((data.flight_time_ms / 1000) * (data.fps || 30));
        const fpsVal = data.fps || 30.0;
        const timeSec = (data.flight_time_ms / 1000.0);
        const distFt = getSelectedDistance();

        if (proofFramesCount) proofFramesCount.textContent = `${elapsedFrames} frames`;
        if (proofTimeStr) proofTimeStr.textContent = `${timeSec.toFixed(3)}s (${Math.round(data.flight_time_ms)} ms) [${elapsedFrames} frames @ ${fpsVal.toFixed(1)} fps]`;
        if (proofDistStr) proofDistStr.textContent = `${distFt.toFixed(1)} ft (${(distFt * 0.3048).toFixed(1)} m)`;
        if (proofFormulaStr) proofFormulaStr.textContent = `${distFt.toFixed(1)} ft / ${timeSec.toFixed(3)}s × 0.6818 = ${data.velocity_mph.toFixed(1)} MPH`;

        // Kinematics Micro-Cards
        flightTimeVal.textContent = Math.round(data.flight_time_ms);
        // break inches need a real scale: unknown until the zone is calibrated
        const brk = (v) => data.zone_calibrated === false ? '—' : (v >= 0 ? '+' : '') + v.toFixed(1);
        vertBreakVal.textContent = brk(data.vert_break_in);
        horzBreakVal.textContent = brk(data.horz_break_in);
        
        const pitchDetected = data.pitch_detected ?? Boolean(data.trajectory?.length);
        const isNormal = activeTrackingMode === 'normal' || data.mode === 'normal';
        const tag = pitchDetected ? (data.pitch_tag || (isNormal ? 'Ball Flight' : 'Pitch')) : 'No Pitch';
        sidePitchType.textContent = tag;

        if (data.mode) {
            setTrackingMode(data.mode);
        }

        // On-Video Glassmorphism Overlay
        overlayPitchNum.textContent = isNormal ? 'BALL FLIGHT' : `PITCH #${data.pitch_number || 1}`;
        overlayPitchTag.textContent = tag;
        overlayVelocityVal.textContent = data.velocity_mph.toFixed(1);
        
        if (isHudVisible) {
            videoOverlayPill.classList.remove('opacity-0');
            videoOverlayCall.classList.remove('opacity-0');
        }

        // Call State
        updateCallState(data.is_strike, pitchDetected, data.zone_calibrated !== false);

        // Synchronize Strike Zone
        if (data.strike_zone && data.show_strike_zone !== false && activeTrackingMode !== 'normal') {
            const cx = (data.strike_zone.x_min + data.strike_zone.x_max) / 2.0;
            const cy = (data.strike_zone.y_min + data.strike_zone.y_max) / 2.0;
            const w = data.strike_zone.x_max - data.strike_zone.x_min;
            const h = data.strike_zone.y_max - data.strike_zone.y_min;
            strikeZone = { cx, cy, w, h };
            syncInteractiveBox();
        } else if (interactiveZoneBox) {
            interactiveZoneBox.classList.add('hidden');
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

    // 15. Fast Re-Render (~1s) on Strike Zone or Visual Change
    async function applyStrikeZoneChanges(extra = {}) {
        if (!currentPitchData?.trajectory?.length) {
            alert('A verified pitch is required before calibrating the strike zone.');
            return;
        }

        loadingOverlay.classList.remove('hidden');
        loadingStatusText.textContent = 'Re-rendering Strike Zone & Streamline (~1s)...';

        const ballType = ballTypeSelect?.value || 'auto';
        const trimPitch = trimPitchCheckbox?.checked ?? false;
        const hudStyle = cleanVideoCheckbox?.checked ? 'none' : 'minimal_badge';

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
            graphic_style: activeGraphicStyle,
            ball_type: ballType,
            perspective: activePerspective,
            pitch_number: currentPitchData.pitch_number || 1,
            trim_to_pitch: trimPitch,
            hud_style: hudStyle,
            mode: activeTrackingMode,
            batter_height_in: Number(dockBatterHeight.value) || 72,
            ...extra,
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
            setCalibrationMode(false);
        } catch (err) {
            alert('Re-render error: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    applyZoneChangesBtn.addEventListener('click', () => applyStrikeZoneChanges());
    dockApplyBtn.addEventListener('click', () => applyStrikeZoneChanges());

    // 15b. Plate calibration: tap the plate's two front corners (17in apart) on a paused frame
    let plateTaps = null;  // null = not tapping; else corners collected so far, in rendered-video pixels

    function clientToVideoPx(e) {
        const r = video.getBoundingClientRect();  // includes the zoom transform; video is object-fit: contain
        const { vidW, vidH } = getVideoRenderedGeometry();
        const s = Math.min(r.width / vidW, r.height / vidH);
        const x = (e.clientX - (r.left + (r.width - vidW * s) / 2)) / s;
        const y = (e.clientY - (r.top + (r.height - vidH * s) / 2)) / s;
        return (x >= 0 && x <= vidW && y >= 0 && y <= vidH) ? [x, y] : null;
    }

    dockCancelBtn.addEventListener('click', () => {
        plateTaps = null;
        dockTapPlateBtn.textContent = 'Tap plate';
    });

    dockTapPlateBtn.addEventListener('click', () => {
        video.pause();
        plateTaps = [];
        dockTapPlateBtn.textContent = 'Tap left front corner';
    });

    videoDropZone.addEventListener('click', (e) => {
        if (plateTaps === null || e.target.closest('button') || e.target.closest('#zoneCalibrationDock')) return;
        const pt = clientToVideoPx(e);
        if (!pt) return;
        plateTaps.push(pt);
        if (plateTaps.length < 2) {
            dockTapPlateBtn.textContent = 'Tap right front corner';
            return;
        }
        const corners = plateTaps;
        plateTaps = null;
        dockTapPlateBtn.textContent = 'Tap plate';
        applyStrikeZoneChanges({ plate_corners: corners });
    });

    // 16. Upload & Process Video Workflow
    // Live progress while /api/process runs: elapsed ticks locally, stage/percent polled from the server
    function startProgress(jobId) {
        const bar = document.getElementById('loadingBar');
        const timer = document.getElementById('loadingTimer');
        document.getElementById('loadingProgress').classList.remove('hidden');
        const t0 = performance.now();
        let pct = 0;
        const fmt = (s) => s >= 60 ? `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s` : `${s.toFixed(1)}s`;
        const tick = setInterval(() => {
            const elapsed = (performance.now() - t0) / 1000;
            const eta = pct >= 5 && pct < 100 ? ` · ~${fmt(elapsed * (100 - pct) / pct)} left` : '';
            timer.textContent = `${pct}% · ${fmt(elapsed)} elapsed${eta}`;
        }, 200);
        const poll = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress/${jobId}`);
                if (!res.ok) return;
                const p = await res.json();
                pct = p.pct;
                bar.style.width = `${pct}%`;
                loadingStatusText.textContent = `${p.stage}...`;
            } catch (e) { /* server busy; next poll */ }
        }, 1000);
        return () => {
            clearInterval(tick);
            clearInterval(poll);
            bar.style.width = '0%';
            timer.textContent = '';
            document.getElementById('loadingProgress').classList.add('hidden');
        };
    }

    async function uploadAndProcessVideo(file, pitchWindow = null) {
        loadingOverlay.classList.remove('hidden');
        loadingStatusText.textContent = 'Uploading...';
        const jobId = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, '0')).join('');
        const stopProgress = startProgress(jobId);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('distance_ft', getSelectedDistance());
        formData.append('pitch_number', 1);
        formData.append('graphic_style', activeGraphicStyle);
        formData.append('ball_type', ballTypeSelect?.value || 'auto');
        formData.append('perspective', activePerspective);
        formData.append('trim_to_pitch', trimPitchCheckbox?.checked ?? false);
        formData.append('hud_style', cleanVideoCheckbox?.checked ? 'none' : 'minimal_badge');
        formData.append('mode', activeTrackingMode);
        formData.append('job_id', jobId);
        if (pitchWindow) {
            formData.append('start_s', pitchWindow.start);
            formData.append('end_s', pitchWindow.end);
        }

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
            const took = document.getElementById('processingTimeVal');
            if (took && data.processing_time_s != null) took.textContent = `Processed in ${data.processing_time_s.toFixed(1)}s on ${data.compute || 'this computer'}`;
        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            stopProgress();
            loadingOverlay.classList.add('hidden');
        }
    }

    // 16b. Pitch window: preview the chosen clip, mark start/end around the pitch, then process only that.
    // Tracking cost scales with frames searched, so a 1.5s window on a 5s clip is ~3x faster.
    const trimDock = document.getElementById('trimDock');
    let pendingClip = null;  // {file, url, start, end}

    function stageClip(file) {
        if (pendingClip) URL.revokeObjectURL(pendingClip.url);
        pendingClip = { file, url: URL.createObjectURL(file), start: 0, end: null };
        if (emptyState) emptyState.classList.add('hidden');
        video.src = pendingClip.url;
        video.load();
        document.getElementById('trimStartVal').textContent = '0.00s';
        document.getElementById('trimEndVal').textContent = '--';
        trimDock.classList.remove('hidden');
    }

    function processStaged(useWindow) {
        if (!pendingClip) return;
        const clip = pendingClip;
        const end = clip.end ?? video.duration;
        if (useWindow && !(end > clip.start)) {
            alert('Set the end after the start.');
            return;
        }
        trimDock.classList.add('hidden');
        pendingClip = null;
        uploadAndProcessVideo(clip.file, useWindow ? { start: clip.start, end } : null)
            .finally(() => URL.revokeObjectURL(clip.url));
    }

    document.getElementById('trimStartBtn').addEventListener('click', () => {
        if (!pendingClip) return;
        pendingClip.start = video.currentTime;
        document.getElementById('trimStartVal').textContent = `${video.currentTime.toFixed(2)}s`;
    });
    document.getElementById('trimEndBtn').addEventListener('click', () => {
        if (!pendingClip) return;
        pendingClip.end = video.currentTime;
        document.getElementById('trimEndVal').textContent = `${video.currentTime.toFixed(2)}s`;
    });
    document.getElementById('trimProcessBtn').addEventListener('click', () => processStaged(true));
    document.getElementById('trimWholeBtn').addEventListener('click', () => processStaged(false));

    videoUploadInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            stageClip(e.target.files[0]);
            e.target.value = '';  // choosing the same file again still fires
        }
    });

    // 17. Drag & Drop on Viewport
    ['dragenter', 'dragover'].forEach(name => {
        videoDropZone.addEventListener(name, (e) => {
            e.preventDefault();
            videoDropZone.classList.add('border-pitchcyan');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        videoDropZone.addEventListener(name, (e) => {
            e.preventDefault();
            videoDropZone.classList.remove('border-pitchcyan');
        });
    });

    videoDropZone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            stageClip(e.dataTransfer.files[0]);
        }
    });

    // 18. Sample Pitch Demo
    samplePitchBtn.addEventListener('click', async () => {
        loadingOverlay.classList.remove('hidden');
        loadingStatusText.textContent = 'Processing Demo Pitch...';
        try {
            const response = await fetch('/api/sample');
            if (!response.ok) throw new Error('Failed to load sample pitch');
            const data = await response.json();
            updateTelemetry(data);
        } catch (err) {
            alert('Could not load demo pitch: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });

    // 19. Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
        // Ignore if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

        if (e.code === 'Space') {
            e.preventDefault();
            playPauseBtn.click();
        } else if (e.code === 'ArrowLeft') {
            e.preventDefault();
            stepBackBtn.click();
        } else if (e.code === 'ArrowRight') {
            e.preventDefault();
            stepForwardBtn.click();
        } else if (e.key === 'z' || e.key === 'Z') {
            e.preventDefault();
            setCalibrationMode(!isZoneCalibrating);
        } else if (e.key === 'x' || e.key === 'X') {
            e.preventDefault();
            toggleZoneZoom();
        } else if (e.code === 'Escape') {
            if (currentZoom > 1.0) {
                applyZoom(1.0, true);
            }
            if (isZoneCalibrating) {
                setCalibrationMode(false);
            }
            helpModal.classList.add('hidden');
        }
    });

    // 20. Help Modal
    helpModalBtn.addEventListener('click', () => helpModal.classList.remove('hidden'));
    closeHelpModalBtn.addEventListener('click', () => helpModal.classList.add('hidden'));
    helpModal.addEventListener('click', (e) => {
        if (e.target === helpModal) helpModal.classList.add('hidden');
    });
});
