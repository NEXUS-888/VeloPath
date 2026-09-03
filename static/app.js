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
    const coveragePct = document.getElementById('coveragePct');
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
    const dockCallStatus = document.getElementById('dockCallStatus');
    const videoZoneToggleBtn = document.getElementById('videoZoneToggleBtn');
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

    // Modals
    const helpModal = document.getElementById('helpModal');
    const helpModalBtn = document.getElementById('helpModalBtn');
    const closeHelpModalBtn = document.getElementById('closeHelpModalBtn');

    // State Variables
    let currentPitchData = null;
    let isZoneCalibrating = false;
    let isHudVisible = true;
    let activeGraphicStyle = 'statcast_cyan';
    let activePerspective = 'behind_pitcher';

    // Active Strike Zone Geometry in native video pixels
    let strikeZone = {
        cx: 540,
        cy: 960,
        w: 180,
        h: 210
    };

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

        if (persp === 'broadcast') {
            strikeZone = {
                cx: Math.round(vidW * 0.558),
                cy: Math.round(vidH * 0.405),
                w: Math.round(vidW * 0.062),
                h: Math.round(vidH * 0.116),
            };
        } else if (persp === 'behind_plate') {
            strikeZone = {
                cx: Math.round(vidW * 0.50),
                cy: Math.round(vidH * 0.68),
                w: Math.round(vidW * 0.22),
                h: Math.round(vidH * 0.18),
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

    // 10. Coordinate Mapping for Clean Strike Zone Box
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
        const ballR = 14.0;

        const isStrike = (px >= x_min - ballR) && (px <= x_max + ballR) &&
                         (py >= y_min - ballR) && (py <= y_max + ballR);

        updateCallState(isStrike);
    }

    function updateCallState(isStrike) {
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

    window.addEventListener('resize', syncInteractiveBox);

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

        const plateMph = data.plate_velocity_mph || (data.velocity_mph * 0.95);
        const plateKmh = data.plate_velocity_kmh || (plateMph * 1.60934);
        if (plateVelocityVal) plateVelocityVal.textContent = plateMph.toFixed(1);
        if (plateVelocityKmh) plateVelocityKmh.textContent = plateKmh.toFixed(1);

        const dragLoss = ((data.velocity_mph - plateMph) / Math.max(1, data.velocity_mph)) * 100.0;
        if (dragLossPct) dragLossPct.textContent = `-${dragLoss.toFixed(1)}%`;
        const covPct = Math.round((data.coverage_fraction || 1.0) * 100);
        if (coveragePct) coveragePct.textContent = `${covPct}%`;

        // Kinematics Micro-Cards
        flightTimeVal.textContent = Math.round(data.flight_time_ms);
        vertBreakVal.textContent = (data.vert_break_in >= 0 ? '+' : '') + data.vert_break_in.toFixed(1);
        horzBreakVal.textContent = (data.horz_break_in >= 0 ? '+' : '') + data.horz_break_in.toFixed(1);
        
        const tag = data.pitch_tag || 'Fastball';
        sidePitchType.textContent = tag;

        // On-Video Glassmorphism Overlay
        overlayPitchNum.textContent = `PITCH #${data.pitch_number || 1}`;
        overlayPitchTag.textContent = tag;
        overlayVelocityVal.textContent = data.velocity_mph.toFixed(1);
        
        if (isHudVisible) {
            videoOverlayPill.classList.remove('opacity-0');
            videoOverlayCall.classList.remove('opacity-0');
        }

        // Call State
        updateCallState(data.is_strike);

        // Synchronize Strike Zone
        if (data.strike_zone) {
            const cx = (data.strike_zone.x_min + data.strike_zone.x_max) / 2.0;
            const cy = (data.strike_zone.y_min + data.strike_zone.y_max) / 2.0;
            const w = data.strike_zone.x_max - data.strike_zone.x_min;
            const h = data.strike_zone.y_max - data.strike_zone.y_min;
            strikeZone = { cx, cy, w, h };
            syncInteractiveBox();
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
    async function applyStrikeZoneChanges() {
        if (!currentPitchData || !currentPitchData.trajectory) {
            alert('Please load or upload a pitch video first.');
            return;
        }

        loadingOverlay.classList.remove('hidden');
        loadingStatusText.textContent = 'Re-rendering Strike Zone & Streamline (~1s)...';

        const ballType = ballTypeSelect?.value || 'auto';
        const trimPitch = trimPitchCheckbox?.checked ?? true;
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

    applyZoneChangesBtn.addEventListener('click', applyStrikeZoneChanges);
    dockApplyBtn.addEventListener('click', applyStrikeZoneChanges);

    // 16. Upload & Process Video Workflow
    async function uploadAndProcessVideo(file) {
        loadingOverlay.classList.remove('hidden');
        loadingStatusText.textContent = 'Tracking Pitch Trajectory & Speed...';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('distance_ft', getSelectedDistance());
        formData.append('pitch_number', 1);
        formData.append('graphic_style', activeGraphicStyle);
        formData.append('ball_type', ballTypeSelect?.value || 'auto');
        formData.append('perspective', activePerspective);
        formData.append('trim_to_pitch', trimPitchCheckbox?.checked ?? true);
        formData.append('hud_style', cleanVideoCheckbox?.checked ? 'none' : 'minimal_badge');

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
            uploadAndProcessVideo(e.dataTransfer.files[0]);
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
        } else if (e.code === 'Escape') {
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
