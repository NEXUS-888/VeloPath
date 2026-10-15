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

    // View Switching & Landing Elements
    const landingView = document.getElementById('landingView');
    const studioView = document.getElementById('studioView');
    const scorebookView = document.getElementById('scorebookView');
    const viewOverviewBtn = document.getElementById('viewOverviewBtn');
    const viewStudioBtn = document.getElementById('viewStudioBtn');
    const viewScoreBtn = document.getElementById('viewScoreBtn');
    const studioToScorebookBtn = document.getElementById('studioToScorebookBtn');
    const studioMatchTitle = document.getElementById('studioMatchTitle');
    const studioMatchInning = document.getElementById('studioMatchInning');
    const studioMatchCount = document.getElementById('studioMatchCount');
    const studioMatchOuts = document.getElementById('studioMatchOuts');
    const studioMatchScore = document.getElementById('studioMatchScore');
    const landingDemoBtn = document.getElementById('landingDemoBtn');
    const landingUploadBtn = document.getElementById('landingUploadBtn');
    const landingExploreStudioBtn = document.getElementById('landingExploreStudioBtn');
    const landingDropZone = document.getElementById('landingDropZone');
    const landingPresetBtns = document.querySelectorAll('.landing-preset-btn');

    // Teaser Pitch Elements
    const teaserPitchFastball = document.getElementById('teaserPitchFastball');
    const teaserPitchSlider = document.getElementById('teaserPitchSlider');
    const teaserPitchCurve = document.getElementById('teaserPitchCurve');
    const teaserReplayBtn = document.getElementById('teaserReplayBtn');
    const teaserLaunchStudioBtn = document.getElementById('teaserLaunchStudioBtn');
    const teaserVelocityVal = document.getElementById('teaserVelocityVal');
    const teaserPlateVal = document.getElementById('teaserPlateVal');
    const teaserDragVal = document.getElementById('teaserDragVal');
    const teaserCallBadge = document.getElementById('teaserCallBadge');
    const teaserFlightPath = document.getElementById('teaserFlightPath');
    const teaserImpactCircle = document.getElementById('teaserImpactCircle');
    const teaserImpactInner = document.getElementById('teaserImpactInner');

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
    // True once the zone is real: set by the user (drag, Apply, plate taps) or calibrated by the server.
    // Until then the box is only a starting guess and must not be sent, or the server would make a call on it.
    let zoneUserSet = false;

    function setTrackingMode(mode) {
        activeTrackingMode = mode;
        if (mode === 'normal') {
            if (modeNormalBtn) modeNormalBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-bold bg-pitchcyan text-black shadow-sm transition flex items-center gap-1.5';
            if (modeBaseballBtn) modeBaseballBtn.className = 'mode-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
            if (modeStatusPill) {
                modeStatusPill.textContent = 'FULL-FRAME MOTION';
                modeStatusPill.className = 'text-[10px] font-mono font-bold text-pitchcyan px-2 py-0.5 rounded bg-pitchcyan/10 border border-pitchcyan/20 uppercase tracking-wider';
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
                modeStatusPill.textContent = 'ABS STRIKE ZONE';
                modeStatusPill.className = 'text-[10px] font-mono font-bold text-pitchcyan px-2 py-0.5 rounded bg-pitchcyan/10 border border-pitchcyan/20 uppercase tracking-wider';
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

    // 2b. View Switching (Landing Overview vs Pro Studio vs Scorebook)
    const BTN_ACTIVE_CLS = 'view-btn px-2.5 py-1 rounded text-xs font-bold bg-pitchcyan text-black shadow-sm transition flex items-center gap-1.5';
    const BTN_INACTIVE_CLS = 'view-btn px-2.5 py-1 rounded text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';

    function switchView(viewName) {
        if (viewName === 'studio') {
            if (landingView) landingView.classList.add('hidden');
            if (scorebookView) scorebookView.classList.add('hidden');
            if (studioView) studioView.classList.remove('hidden');
            if (viewOverviewBtn) viewOverviewBtn.className = BTN_INACTIVE_CLS;
            if (viewStudioBtn) viewStudioBtn.className = BTN_ACTIVE_CLS;
            if (viewScoreBtn) viewScoreBtn.className = BTN_INACTIVE_CLS;
            setTimeout(() => {
                syncInteractiveBox();
            }, 60);
        } else if (viewName === 'scorebook') {
            if (landingView) landingView.classList.add('hidden');
            if (studioView) studioView.classList.add('hidden');
            if (scorebookView) scorebookView.classList.remove('hidden');
            if (viewOverviewBtn) viewOverviewBtn.className = BTN_INACTIVE_CLS;
            if (viewStudioBtn) viewStudioBtn.className = BTN_INACTIVE_CLS;
            if (viewScoreBtn) viewScoreBtn.className = BTN_ACTIVE_CLS;
        } else {
            if (studioView) studioView.classList.add('hidden');
            if (scorebookView) scorebookView.classList.add('hidden');
            if (landingView) landingView.classList.remove('hidden');
            if (viewOverviewBtn) viewOverviewBtn.className = BTN_ACTIVE_CLS;
            if (viewStudioBtn) viewStudioBtn.className = BTN_INACTIVE_CLS;
            if (viewScoreBtn) viewScoreBtn.className = BTN_INACTIVE_CLS;
        }
        if (window.lucide) window.lucide.createIcons();
    }

    if (viewOverviewBtn) viewOverviewBtn.addEventListener('click', () => switchView('overview'));
    if (viewStudioBtn) viewStudioBtn.addEventListener('click', () => switchView('studio'));
    if (viewScoreBtn) viewScoreBtn.addEventListener('click', () => switchView('scorebook'));
    if (studioToScorebookBtn) studioToScorebookBtn.addEventListener('click', () => switchView('scorebook'));
    if (landingExploreStudioBtn) landingExploreStudioBtn.addEventListener('click', () => switchView('studio'));

    // Teaser Pitch Presets & Simulation
    const TEASER_PITCHES = {
        fastball: {
            velocity: '99.4',
            plate: '91.8',
            drag: '-7.6%',
            callText: 'STRIKE (Quadrant 3)',
            callClass: 'text-xs font-black tracking-wider uppercase px-2.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 glow-emerald',
            pathD: 'M 480 220 Q 484 310 495 355',
            impactX: 495,
            impactY: 355,
            impactColor: '#00E676'
        },
        slider: {
            velocity: '86.2',
            plate: '79.1',
            drag: '-8.2%',
            callText: 'STRIKE (Quadrant 9)',
            callClass: 'text-xs font-black tracking-wider uppercase px-2.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 glow-emerald',
            pathD: 'M 480 220 Q 498 300 545 420',
            impactX: 545,
            impactY: 420,
            impactColor: '#00E676'
        },
        curve: {
            velocity: '81.5',
            plate: '73.4',
            drag: '-9.9%',
            callText: 'BALL (Below Zone)',
            callClass: 'text-xs font-black tracking-wider uppercase px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40',
            pathD: 'M 480 220 Q 476 300 460 495',
            impactX: 460,
            impactY: 495,
            impactColor: '#F59E0B'
        }
    };

    function selectTeaserPitch(pitchKey) {
        const p = TEASER_PITCHES[pitchKey];
        if (!p) return;

        // Button states
        const teaserPitchBtns = [
            { btn: teaserPitchFastball, key: 'fastball' },
            { btn: teaserPitchSlider, key: 'slider' },
            { btn: teaserPitchCurve, key: 'curve' }
        ];
        teaserPitchBtns.forEach(({ btn, key }) => {
            if (!btn) return;
            if (key === pitchKey) {
                btn.className = 'teaser-pitch-btn px-2.5 py-1 rounded-lg text-xs font-bold bg-pitchcyan text-black shadow-sm transition';
            } else {
                btn.className = 'teaser-pitch-btn px-2.5 py-1 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition';
            }
        });

        // Update telemetry display
        if (teaserVelocityVal) teaserVelocityVal.textContent = p.velocity;
        if (teaserPlateVal) teaserPlateVal.textContent = p.plate;
        if (teaserDragVal) teaserDragVal.textContent = p.drag;
        if (teaserCallBadge) {
            teaserCallBadge.textContent = p.callText;
            teaserCallBadge.className = p.callClass;
        }

        // Update SVG paths and impact points
        if (teaserFlightPath) teaserFlightPath.setAttribute('d', p.pathD);
        if (teaserImpactCircle) {
            teaserImpactCircle.setAttribute('cx', p.impactX);
            teaserImpactCircle.setAttribute('cy', p.impactY);
            teaserImpactCircle.setAttribute('fill', p.impactColor);
        }
        if (teaserImpactInner) {
            teaserImpactInner.setAttribute('cx', p.impactX);
            teaserImpactInner.setAttribute('cy', p.impactY);
        }

        replayTeaserFlight();
    }

    function replayTeaserFlight() {
        if (!teaserFlightPath) return;
        try {
            const pathLen = teaserFlightPath.getTotalLength ? (teaserFlightPath.getTotalLength() || 250) : 250;
            teaserFlightPath.style.transition = 'none';
            teaserFlightPath.style.strokeDasharray = `${pathLen}`;
            teaserFlightPath.style.strokeDashoffset = `${pathLen}`;
            if (teaserImpactCircle) teaserImpactCircle.style.opacity = '0';
            if (teaserImpactInner) teaserImpactInner.style.opacity = '0';

            requestAnimationFrame(() => {
                teaserFlightPath.style.transition = 'stroke-dashoffset 0.65s cubic-bezier(0.25, 0.1, 0.25, 1)';
                teaserFlightPath.style.strokeDashoffset = '0';
                setTimeout(() => {
                    if (teaserImpactCircle) {
                        teaserImpactCircle.style.transition = 'opacity 0.2s ease';
                        teaserImpactCircle.style.opacity = '1';
                    }
                    if (teaserImpactInner) {
                        teaserImpactInner.style.transition = 'opacity 0.2s ease';
                        teaserImpactInner.style.opacity = '0.6';
                    }
                }, 600);
            });
        } catch (e) {
            if (teaserImpactCircle) teaserImpactCircle.style.opacity = '1';
            if (teaserImpactInner) teaserImpactInner.style.opacity = '0.6';
        }
    }

    if (teaserPitchFastball) teaserPitchFastball.addEventListener('click', () => selectTeaserPitch('fastball'));
    if (teaserPitchSlider) teaserPitchSlider.addEventListener('click', () => selectTeaserPitch('slider'));
    if (teaserPitchCurve) teaserPitchCurve.addEventListener('click', () => selectTeaserPitch('curve'));
    if (teaserReplayBtn) teaserReplayBtn.addEventListener('click', replayTeaserFlight);
    if (teaserLaunchStudioBtn) {
        teaserLaunchStudioBtn.addEventListener('click', () => {
            switchView('studio');
            if (samplePitchBtn) samplePitchBtn.click();
        });
    }

    // Landing Hub Actions
    if (landingDemoBtn) {
        landingDemoBtn.addEventListener('click', () => {
            switchView('studio');
            if (samplePitchBtn) samplePitchBtn.click();
        });
    }

    if (landingUploadBtn) {
        landingUploadBtn.addEventListener('click', () => {
            if (videoUploadInput) videoUploadInput.click();
        });
    }

    if (landingDropZone) {
        landingDropZone.addEventListener('click', () => {
            if (videoUploadInput) videoUploadInput.click();
        });
        ['dragenter', 'dragover'].forEach(name => {
            landingDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                landingDropZone.classList.add('border-pitchcyan', 'bg-slate-900/90');
            });
        });
        ['dragleave', 'drop'].forEach(name => {
            landingDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                landingDropZone.classList.remove('border-pitchcyan', 'bg-slate-900/90');
            });
        });
        landingDropZone.addEventListener('drop', (e) => {
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                stageClip(e.dataTransfer.files[0]);
            }
        });
    }

    // Quick-Start Preset Buttons
    landingPresetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const dist = btn.getAttribute('data-preset-dist');
            const mode = btn.getAttribute('data-preset-mode');
            const ball = btn.getAttribute('data-preset-ball');

            if (dist) {
                if (distancePresetSelect) {
                    distancePresetSelect.value = dist;
                    if (dist === 'custom') {
                        if (customDistanceRow) customDistanceRow.classList.remove('hidden');
                    } else {
                        if (customDistanceRow) customDistanceRow.classList.add('hidden');
                    }
                }
            }

            if (mode) {
                setTrackingMode(mode);
            }

            if (ball && ballTypeSelect) {
                ballTypeSelect.value = ball;
            }

            switchView('studio');
        });
    });

    // Run initial teaser flight animation once ready
    setTimeout(replayTeaserFlight, 300);

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
        if (!currentPitchData?.plate_crossing || !zoneUserSet) return;  // no live call on a guessed box
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

        zoneUserSet = true;
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
        const is3d = data.measurement === '3d';
        const setLabel = (id, text, title) => { const el = document.getElementById(id); if (el) { el.textContent = text; el.title = title; } };
        setLabel('vertBreakLabel', is3d ? 'Induced Vert. Break (3D)' : 'Vertical Break (est.)',
                 is3d ? '3D fit from plate + rubber taps: movement from spin, gravity removed. + = rise'
                      : '2D estimate: how far the path bows on screen. Tap plate + rubber for 3D. + = drop');
        setLabel('horzBreakLabel', is3d ? 'Horizontal Break (3D)' : 'Horizontal Break (est.)',
                 is3d ? "3D fit: sideways movement from spin, + = catcher's right" : '2D estimate; tap plate + rubber for 3D');
        setLabel('pitchTypeLabel', 'Pitch Type', is3d ? 'From 3D speed and break' : 'Needs plate + rubber taps (3D) to name the pitch');
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
        zoneUserSet = data.zone_calibrated === true;

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

        // Score confirm bar feed (Phase C)
        if (typeof scoreOfferConfirm === 'function') {
            scoreOfferConfirm(data);
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
            custom_strike_zone: zoneUserSet ? {
                x_min: strikeZone.cx - (strikeZone.w / 2.0),
                y_min: strikeZone.cy - (strikeZone.h / 2.0),
                x_max: strikeZone.cx + (strikeZone.w / 2.0),
                y_max: strikeZone.cy + (strikeZone.h / 2.0),
            } : null,
            graphic_style: activeGraphicStyle,
            ball_type: ballType,
            perspective: activePerspective,
            pitch_number: currentPitchData.pitch_number || 1,
            trim_to_pitch: trimPitch,
            hud_style: hudStyle,
            mode: activeTrackingMode,
            batter_height_in: Number(dockBatterHeight.value) || 72,
            ...(calibrationTaps || {}),
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

    // Apply = "this box is my zone"; theme / distance changes re-render without claiming a zone
    applyZoneChangesBtn.addEventListener('click', () => { zoneUserSet = true; applyStrikeZoneChanges(); });
    dockApplyBtn.addEventListener('click', () => { zoneUserSet = true; applyStrikeZoneChanges(); });

    // 15b. Calibration taps on a paused frame: plate front corners (17in) -> real zone;
    // + rubber ends (24in, 60.5 ft away) -> 3D speed and break. Remembered for later re-renders of this clip.
    let plateTaps = null;  // null = not tapping; else points collected so far, in rendered-video pixels
    let calibrationTaps = null;  // {plate_corners, rubber_corners?} sent with every re-render once set
    const TAP_STEPS = ['Tap plate: left front corner', 'Tap plate: right front corner',
                       'Tap rubber: left end (click here to skip)', 'Tap rubber: right end (click here to skip)'];

    function clientToVideoPx(e) {
        const r = video.getBoundingClientRect();  // includes the zoom transform; video is object-fit: contain
        const { vidW, vidH } = getVideoRenderedGeometry();
        const s = Math.min(r.width / vidW, r.height / vidH);
        const x = (e.clientX - (r.left + (r.width - vidW * s) / 2)) / s;
        const y = (e.clientY - (r.top + (r.height - vidH * s) / 2)) / s;
        return (x >= 0 && x <= vidW && y >= 0 && y <= vidH) ? [x, y] : null;
    }

    function finishTaps() {
        const t = plateTaps;
        plateTaps = null;
        dockTapPlateBtn.textContent = 'Tap plate';
        calibrationTaps = { plate_corners: t.slice(0, 2), ...(t.length === 4 ? { rubber_corners: t.slice(2, 4) } : {}) };
        zoneUserSet = false;  // the fresh plate taps define the zone (a hand-dragged box would win otherwise)
        applyStrikeZoneChanges();
    }

    dockCancelBtn.addEventListener('click', () => {
        plateTaps = null;
        dockTapPlateBtn.textContent = 'Tap plate';
    });

    dockTapPlateBtn.addEventListener('click', () => {
        if (plateTaps !== null && plateTaps.length >= 2) {  // during the rubber taps: skip them (zone only, no 3D)
            plateTaps = plateTaps.slice(0, 2);
            finishTaps();
            return;
        }
        video.pause();
        plateTaps = [];
        dockTapPlateBtn.textContent = TAP_STEPS[0];
    });

    videoDropZone.addEventListener('click', (e) => {
        if (plateTaps === null || e.target.closest('button') || e.target.closest('#zoneCalibrationDock')) return;
        const pt = clientToVideoPx(e);
        if (!pt) return;
        plateTaps.push(pt);
        if (plateTaps.length < 4) {
            dockTapPlateBtn.textContent = TAP_STEPS[plateTaps.length];
            return;
        }
        finishTaps();
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
        const ext = (file && file.name) ? file.name.split('.').pop().toLowerCase().replace(/[^a-z0-9]/g, '') : 'mp4';
        const safeName = `pitch_upload.${ext || 'mp4'}`;
        formData.append('file', file, safeName);
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
                const err = await response.json().catch(() => ({}));
                const msg = typeof err.detail === 'string'
                    ? err.detail
                    : (Array.isArray(err.detail) ? err.detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'Video processing failed');
                throw new Error(msg);
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
        switchView('studio');
        if (pendingClip) URL.revokeObjectURL(pendingClip.url);
        pendingClip = { file, url: URL.createObjectURL(file), start: 0, end: null };
        calibrationTaps = null;  // taps belong to the previous clip's camera
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
        switchView('studio');
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

    // 21. Scorekeeping Controller (Phase B)
    let scoreCurrentGameId = null;
    let scoreCurrentState = null;

    // DOM Elements
    const scoreCard = document.getElementById('scoreCard');
    const scoreNewBtn = document.getElementById('scoreNewBtn');
    const scoreSetup = document.getElementById('scoreSetup');
    const scoreAway = document.getElementById('scoreAway');
    const scoreHome = document.getElementById('scoreHome');
    const scoreInnings = document.getElementById('scoreInnings');
    const scoreStartBtn = document.getElementById('scoreStartBtn');
    const scoreDisplay = document.getElementById('scoreDisplay');
    const scoreInningLabel = document.getElementById('scoreInningLabel');
    const scoreCount = document.getElementById('scoreCount');
    const scoreOuts = document.getElementById('scoreOuts');
    const scoreDiamond = document.getElementById('scoreDiamond');
    const scoreLine = document.getElementById('scoreLine');
    const scoreFinal = document.getElementById('scoreFinal');
    const scorePitchButtons = document.querySelectorAll('[data-pitch]');
    const scorePlayPicker = document.getElementById('scorePlayPicker');
    const scorePlayButtons = document.querySelectorAll('[data-play]');
    const scoreAdjustBtn = document.getElementById('scoreAdjustBtn');
    const scoreUndoBtn = document.getElementById('scoreUndoBtn');
    const scoreAdjust = document.getElementById('scoreAdjust');
    const scoreBaseButtons = document.querySelectorAll('[data-base]');
    const scoreRunsPlus = document.getElementById('scoreRunsPlus');
    const scoreOutsPlus = document.getElementById('scoreOutsPlus');
    const scoreAdjustApply = document.getElementById('scoreAdjustApply');
    const scoreConfirm = document.getElementById('scoreConfirm');
    const scoreConfirmText = document.getElementById('scoreConfirmText');
    const scoreConfirmAdd = document.getElementById('scoreConfirmAdd');
    const scoreConfirmFoul = document.getElementById('scoreConfirmFoul');
    const scoreConfirmInPlay = document.getElementById('scoreConfirmInPlay');
    const scoreConfirmHbp = document.getElementById('scoreConfirmHbp');
    const scoreConfirmSkip = document.getElementById('scoreConfirmSkip');
    const scoreLogToggle = document.getElementById('scoreLogToggle');
    const scoreLog = document.getElementById('scoreLog');
    const scoreExport = document.getElementById('scoreExport');
    const scoreError = document.getElementById('scoreError');
    const scoreBallByBallFeed = document.getElementById('scoreBallByBallFeed');

    const pitcherNameInput = document.getElementById('pitcherNameInput');
    const pitcherPitchesVal = document.getElementById('pitcherPitchesVal');
    const pitcherStrikesVal = document.getElementById('pitcherStrikesVal');
    const pitcherStrikeRateVal = document.getElementById('pitcherStrikeRateVal');
    const pitcherKsVal = document.getElementById('pitcherKsVal');
    const pitcherBBsVal = document.getElementById('pitcherBBsVal');
    const pitcherRAsVal = document.getElementById('pitcherRAsVal');

    const batterNameInput = document.getElementById('batterNameInput');
    const batterABsVal = document.getElementById('batterABsVal');
    const batterHitsVal = document.getElementById('batterHitsVal');
    const batterAvgVal = document.getElementById('batterAvgVal');
    const batterRunsVal = document.getElementById('batterRunsVal');
    const batterKsVal = document.getElementById('batterKsVal');
    const batterBBsVal = document.getElementById('batterBBsVal');

    let scoreLastAddedVideoId = null;
    let scorePendingPitch = null;

    // Storage helpers
    function scoreGetStoredId() {
        try {
            return localStorage.getItem('velopath.gameId');
        } catch (e) {
            return null;
        }
    }

    function scoreSetStoredId(id) {
        try {
            if (id) {
                localStorage.setItem('velopath.gameId', id);
            } else {
                localStorage.removeItem('velopath.gameId');
            }
        } catch (e) {}
    }

    // Error display helpers
    function scoreShowError(msg) {
        if (!scoreError) return;
        scoreError.textContent = msg;
        scoreError.classList.remove('hidden');
    }

    function scoreHideError() {
        if (!scoreError) return;
        scoreError.textContent = '';
        scoreError.classList.add('hidden');
    }

    // scoreCall helper
    async function scoreCall(path, body) {
        try {
            const opts = {
                method: body !== undefined ? 'POST' : 'GET',
                headers: {}
            };
            if (body !== undefined) {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
            const res = await fetch(path, opts);
            if (!res.ok) {
                let detail = res.statusText || 'Request failed';
                try {
                    const errData = await res.json();
                    if (errData && errData.detail) detail = errData.detail;
                } catch (e) {}
                scoreShowError(detail);
                if (res.status === 404 && path.startsWith('/api/games/')) {
                    scoreSetStoredId(null);
                    scoreCurrentGameId = null;
                    scoreRender(null);
                }
                throw new Error(detail);
            }
            scoreHideError();
            const data = await res.json();
            if (data && data.id) {
                scoreCurrentGameId = data.id;
                scoreSetStoredId(data.id);
            }
            const st = data && data.state ? data.state : data;
            scoreRender(st);
            return st;
        } catch (err) {
            throw err;
        }
    }

    // scoreRender(state)
    function scoreRender(state) {
        scoreCurrentState = state;
        if (!state) {
            if (scoreSetup) scoreSetup.classList.remove('hidden');
            if (scoreDisplay) scoreDisplay.classList.add('hidden');
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            if (scoreExport) {
                scoreExport.href = '#';
                scoreExport.classList.add('pointer-events-none', 'opacity-40');
            }
            if (scoreLog) {
                while (scoreLog.firstChild) scoreLog.removeChild(scoreLog.firstChild);
            }
            if (scoreBallByBallFeed) {
                while (scoreBallByBallFeed.firstChild) scoreBallByBallFeed.removeChild(scoreBallByBallFeed.firstChild);
                const emptyCard = document.createElement('div');
                emptyCard.className = 'p-3 rounded-lg bg-slate-900/60 border border-white/5 text-center text-xs text-slate-400';
                emptyCard.textContent = 'Match initialized. Pitch decisions and plate outcomes will stream live ball-by-ball.';
                scoreBallByBallFeed.appendChild(emptyCard);
            }
            if (pitcherPitchesVal) pitcherPitchesVal.textContent = '0';
            if (pitcherStrikesVal) pitcherStrikesVal.textContent = '0 / 0';
            if (pitcherStrikeRateVal) pitcherStrikeRateVal.textContent = '0.0%';
            if (pitcherKsVal) pitcherKsVal.textContent = '0';
            if (pitcherBBsVal) pitcherBBsVal.textContent = '0';
            if (pitcherRAsVal) pitcherRAsVal.textContent = '0';

            if (batterABsVal) batterABsVal.textContent = '0';
            if (batterHitsVal) batterHitsVal.textContent = '0';
            if (batterAvgVal) batterAvgVal.textContent = '.000';
            if (batterRunsVal) batterRunsVal.textContent = '0';
            if (batterKsVal) batterKsVal.textContent = '0';
            if (batterBBsVal) batterBBsVal.textContent = '0';

            if (studioMatchTitle) studioMatchTitle.textContent = 'Away vs Home';
            if (studioMatchInning) studioMatchInning.textContent = '▲ 1';
            if (studioMatchCount) studioMatchCount.textContent = '0-0';
            if (studioMatchOuts) studioMatchOuts.textContent = '0 Outs';
            if (studioMatchScore) studioMatchScore.textContent = '0 - 0';
            return;
        }

        if (scoreSetup) scoreSetup.classList.add('hidden');
        if (scoreDisplay) scoreDisplay.classList.remove('hidden');

        // 1. Inning label
        if (scoreInningLabel) {
            scoreInningLabel.textContent = (state.top ? '▲ ' : '▼ ') + state.inning;
        }

        // 2. Count
        if (scoreCount) {
            scoreCount.textContent = `${state.balls}-${state.strikes}`;
        }

        // 3. Outs (3 dots)
        if (scoreOuts) {
            while (scoreOuts.firstChild) {
                scoreOuts.removeChild(scoreOuts.firstChild);
            }
            for (let i = 0; i < 3; i++) {
                const dot = document.createElement('span');
                const isOut = i < state.outs;
                dot.className = isOut
                    ? 'w-2.5 h-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50'
                    : 'w-2.5 h-2.5 rounded-full bg-slate-700';
                scoreOuts.appendChild(dot);
            }
        }

        // 4. Diamond SVG bases
        const base0 = document.getElementById('scoreBase0');
        const base1 = document.getElementById('scoreBase1');
        const base2 = document.getElementById('scoreBase2');
        if (base0) {
            const isOcc0 = Boolean(state.bases && state.bases[0]);
            base0.setAttribute('fill', isOcc0 ? '#00f3ff' : 'rgba(255,255,255,0.2)');
            if (isOcc0) {
                base0.classList.add('base-occupied');
                base0.classList.remove('base-empty');
            } else {
                base0.classList.remove('base-occupied');
                base0.classList.add('base-empty');
            }
        }
        if (base1) {
            const isOcc1 = Boolean(state.bases && state.bases[1]);
            base1.setAttribute('fill', isOcc1 ? '#00f3ff' : 'rgba(255,255,255,0.2)');
            if (isOcc1) {
                base1.classList.add('base-occupied');
                base1.classList.remove('base-empty');
            } else {
                base1.classList.remove('base-occupied');
                base1.classList.add('base-empty');
            }
        }
        if (base2) {
            const isOcc2 = Boolean(state.bases && state.bases[2]);
            base2.setAttribute('fill', isOcc2 ? '#00f3ff' : 'rgba(255,255,255,0.2)');
            if (isOcc2) {
                base2.classList.add('base-occupied');
                base2.classList.remove('base-empty');
            } else {
                base2.classList.remove('base-occupied');
                base2.classList.add('base-empty');
            }
        }

        // 5. Final game banner
        if (scoreFinal) {
            if (state.over) {
                const winnerName = state.winner === 'away' ? state.away : (state.winner === 'home' ? state.home : 'Tied');
                scoreFinal.textContent = `Final: ${winnerName} ${state.runs[0]} - ${state.runs[1]}`;
                scoreFinal.classList.remove('hidden');
            } else {
                scoreFinal.textContent = '';
                scoreFinal.classList.add('hidden');
            }
        }

        // 6. Line Score table
        if (scoreLine) {
            while (scoreLine.firstChild) {
                scoreLine.removeChild(scoreLine.firstChild);
            }
            const totalCols = Math.max(state.innings || 9, state.inning || 1);

            // thead
            const thead = document.createElement('thead');
            const headRow = document.createElement('tr');
            headRow.className = 'border-b border-white/10 text-[10px] text-slate-400 font-semibold';

            const thTeam = document.createElement('th');
            thTeam.className = 'py-1 px-2 text-left';
            thTeam.textContent = 'Team';
            headRow.appendChild(thTeam);

            for (let c = 1; c <= totalCols; c++) {
                const th = document.createElement('th');
                th.className = 'py-1 px-1 font-mono';
                th.textContent = String(c);
                headRow.appendChild(th);
            }
            const thR = document.createElement('th');
            thR.className = 'py-1 px-2 font-mono font-bold text-white';
            thR.textContent = 'R';
            headRow.appendChild(thR);
            thead.appendChild(headRow);
            scoreLine.appendChild(thead);

            // tbody
            const tbody = document.createElement('tbody');
            const awayLine = (state.line && state.line.away) || [];
            const homeLine = (state.line && state.line.home) || [];

            // Away row
            const trAway = document.createElement('tr');
            trAway.className = 'border-b border-white/5 text-[11px]';
            const tdAwayName = document.createElement('td');
            tdAwayName.className = 'py-1 px-2 text-left font-bold text-white truncate max-w-[80px]';
            tdAwayName.textContent = state.away || 'Away';
            trAway.appendChild(tdAwayName);

            for (let c = 0; c < totalCols; c++) {
                const td = document.createElement('td');
                td.className = 'py-1 px-1 font-mono text-slate-300';
                if (c < awayLine.length) {
                    td.textContent = String(awayLine[c]);
                } else if (state.over || state.inning > c + 1 || (state.inning === c + 1 && !state.top)) {
                    td.textContent = '0';
                } else {
                    td.textContent = '-';
                }
                trAway.appendChild(td);
            }
            const tdAwayR = document.createElement('td');
            tdAwayR.className = 'py-1 px-2 font-mono font-bold text-pitchcyan';
            tdAwayR.textContent = String(state.runs ? state.runs[0] : 0);
            trAway.appendChild(tdAwayR);
            tbody.appendChild(trAway);

            // Home row
            const trHome = document.createElement('tr');
            trHome.className = 'text-[11px]';
            const tdHomeName = document.createElement('td');
            tdHomeName.className = 'py-1 px-2 text-left font-bold text-white truncate max-w-[80px]';
            tdHomeName.textContent = state.home || 'Home';
            trHome.appendChild(tdHomeName);

            for (let c = 0; c < totalCols; c++) {
                const td = document.createElement('td');
                td.className = 'py-1 px-1 font-mono text-slate-300';
                if (c < homeLine.length) {
                    td.textContent = String(homeLine[c]);
                } else if (state.over && c >= (state.innings || 9) - 1 && homeLine.length <= c && state.runs[1] > state.runs[0]) {
                    td.textContent = 'X';
                } else if (state.over || state.inning > c + 1) {
                    td.textContent = '0';
                } else {
                    td.textContent = '-';
                }
                trHome.appendChild(td);
            }
            const tdHomeR = document.createElement('td');
            tdHomeR.className = 'py-1 px-2 font-mono font-bold text-pitchcyan';
            tdHomeR.textContent = String(state.runs ? state.runs[1] : 0);
            trHome.appendChild(tdHomeR);
            tbody.appendChild(trHome);

            scoreLine.appendChild(tbody);
        }

        // 7. Buttons: awaiting_play & over conditions
        scorePitchButtons.forEach(btn => {
            btn.disabled = Boolean(state.awaiting_play || state.over);
        });

        if (scorePlayPicker) {
            if (state.awaiting_play && !state.over) {
                scorePlayPicker.classList.remove('hidden');
            } else {
                scorePlayPicker.classList.add('hidden');
            }
        }

        if (scoreAdjustBtn) {
            scoreAdjustBtn.disabled = Boolean(state.over);
            if (state.over && scoreAdjust) {
                scoreAdjust.classList.add('hidden');
            }
        }

        scoreBaseButtons.forEach((btn, idx) => {
            const isOcc = Boolean(state.bases && state.bases[idx]);
            btn.dataset.active = isOcc ? 'true' : 'false';
            if (isOcc) {
                btn.classList.add('bg-pitchcyan', 'text-black', 'border-pitchcyan');
                btn.classList.remove('bg-slate-800', 'text-slate-300', 'border-white/10');
            } else {
                btn.classList.remove('bg-pitchcyan', 'text-black', 'border-pitchcyan');
                btn.classList.add('bg-slate-800', 'text-slate-300', 'border-white/10');
            }
        });

        // 8. Confirm bar state sync if open
        const confirmButtons = [scoreConfirmAdd, scoreConfirmFoul, scoreConfirmInPlay, scoreConfirmHbp, scoreConfirmSkip];
        if (state.over) {
            if (scoreConfirmText && scoreConfirm && !scoreConfirm.classList.contains('hidden')) {
                scoreConfirmText.textContent = "Game Over: Pitch not added";
            }
            confirmButtons.forEach(btn => { if (btn) btn.disabled = true; });
        } else if (state.awaiting_play) {
            if (scoreConfirmText && scoreConfirm && !scoreConfirm.classList.contains('hidden')) {
                scoreConfirmText.textContent = "Resolve ball in play before next pitch";
            }
            confirmButtons.forEach(btn => { if (btn) btn.disabled = true; });
        } else {
            confirmButtons.forEach(btn => { if (btn) btn.disabled = false; });
        }

        // 9. Game Log & CSV Export (Phase D)
        if (scoreExport) {
            scoreExport.href = scoreCurrentGameId ? `/api/games/${scoreCurrentGameId}/export.csv` : '#';
            if (scoreCurrentGameId) {
                scoreExport.classList.remove('pointer-events-none', 'opacity-40');
            } else {
                scoreExport.classList.add('pointer-events-none', 'opacity-40');
            }
        }

        if (scoreLog) {
            while (scoreLog.firstChild) {
                scoreLog.removeChild(scoreLog.firstChild);
            }
            const events = (state.log || []).slice(-30).reverse();
            events.forEach(entry => {
                const half = entry.top ? 'Top' : 'Bottom';
                const count = `${entry.balls}-${entry.strikes}`;
                const mphStr = entry.mph !== undefined && entry.mph !== null ? ` | ${entry.mph} mph` : '';
                const item = document.createElement('div');
                item.className = 'text-[11px] text-slate-300 py-0.5 border-b border-white/5 last:border-0 truncate font-mono';
                item.textContent = `${half} ${entry.inning} | ${entry.kind} ${count}${mphStr}`;
                scoreLog.appendChild(item);
            });
        }

        // 10. Live Player Stats & Ball-by-Ball Feed
        scoreComputePlayerStats(state);
        scoreRenderBallByBall(state);

        // 11. Synchronize Studio Dugout Summary Card
        if (studioMatchTitle) {
            studioMatchTitle.textContent = `${state.away || 'Away'} vs ${state.home || 'Home'}`;
        }
        if (studioMatchInning) {
            studioMatchInning.textContent = `${state.top ? '▲' : '▼'} ${state.inning || 1}`;
        }
        if (studioMatchCount) {
            studioMatchCount.textContent = `${state.balls || 0}-${state.strikes || 0}`;
        }
        if (studioMatchOuts) {
            studioMatchOuts.textContent = `${state.outs || 0} Outs`;
        }
        if (studioMatchScore) {
            const awayR = state.runs ? state.runs[0] : 0;
            const homeR = state.runs ? state.runs[1] : 0;
            studioMatchScore.textContent = `${awayR} - ${homeR}`;
        }
    }

    function scoreComputePlayerStats(state) {
        let pitches = 0;
        let strikes = 0;
        let balls = 0;
        let strikeouts = 0;
        let walks = 0;
        let runsAllowed = 0;

        let abs = 0;
        let hits = 0;
        let batterRuns = 0;
        let batterKs = 0;
        let batterBBs = 0;

        const log = (state && state.log) || [];
        for (let i = 0; i < log.length; i++) {
            const ev = log[i];
            const k = ev.kind;
            if (k === 'ball') {
                pitches++;
                balls++;
                if (ev.balls === 3) {
                    walks++;
                    batterBBs++;
                }
            } else if (k === 'strike') {
                pitches++;
                strikes++;
                if (ev.strikes === 2) {
                    strikeouts++;
                    abs++;
                    batterKs++;
                }
            } else if (k === 'foul') {
                pitches++;
                strikes++;
            } else if (k === 'hbp') {
                pitches++;
                walks++;
                batterBBs++;
            } else if (k === 'in_play') {
                pitches++;
                strikes++;
            } else if (k === 'single' || k === 'double' || k === 'triple' || k === 'home_run') {
                abs++;
                hits++;
                if (k === 'home_run') {
                    batterRuns++;
                }
            } else if (k === 'out' || k === 'double_play' || k === 'error') {
                abs++;
            }
        }

        if (state && state.runs) {
            runsAllowed = state.top ? (state.runs[0] || 0) : (state.runs[1] || 0);
        }

        const strikePct = pitches > 0 ? ((strikes / pitches) * 100).toFixed(1) + '%' : '0.0%';
        const avg = abs > 0 ? (hits / abs).toFixed(3).replace(/^0/, '') : '.000';

        if (pitcherPitchesVal) pitcherPitchesVal.textContent = String(pitches);
        if (pitcherStrikesVal) pitcherStrikesVal.textContent = `${strikes} / ${balls}`;
        if (pitcherStrikeRateVal) pitcherStrikeRateVal.textContent = strikePct;
        if (pitcherKsVal) pitcherKsVal.textContent = String(strikeouts);
        if (pitcherBBsVal) pitcherBBsVal.textContent = String(walks);
        if (pitcherRAsVal) pitcherRAsVal.textContent = String(runsAllowed);

        if (batterABsVal) batterABsVal.textContent = String(abs);
        if (batterHitsVal) batterHitsVal.textContent = String(hits);
        if (batterAvgVal) batterAvgVal.textContent = avg;
        if (batterRunsVal) batterRunsVal.textContent = String(batterRuns);
        if (batterKsVal) batterKsVal.textContent = String(batterKs);
        if (batterBBsVal) batterBBsVal.textContent = String(batterBBs);
    }

    function scoreRenderBallByBall(state) {
        if (!scoreBallByBallFeed) return;
        while (scoreBallByBallFeed.firstChild) {
            scoreBallByBallFeed.removeChild(scoreBallByBallFeed.firstChild);
        }

        const log = (state && state.log) || [];
        if (log.length === 0) {
            const emptyCard = document.createElement('div');
            emptyCard.className = 'p-3 rounded-lg bg-slate-900/60 border border-white/5 text-center text-xs text-slate-400';
            emptyCard.textContent = 'Match initialized. Pitch decisions and plate outcomes will stream live ball-by-ball.';
            scoreBallByBallFeed.appendChild(emptyCard);
            return;
        }

        const pName = (pitcherNameInput && pitcherNameInput.value.trim()) || 'Pitcher';
        const bName = (batterNameInput && batterNameInput.value.trim()) || 'Batter';

        const recentEvents = log.slice().reverse();
        recentEvents.forEach((ev, idx) => {
            const seqNum = log.length - idx;
            const card = document.createElement('div');
            card.className = 'p-3 rounded-xl bg-slate-900/80 border border-white/10 hover:border-pitchcyan/30 transition flex flex-col gap-1.5 shadow-sm';

            const headerRow = document.createElement('div');
            headerRow.className = 'flex items-center justify-between text-[11px]';

            const leftInfo = document.createElement('div');
            leftInfo.className = 'flex items-center gap-2';

            const seqBadge = document.createElement('span');
            seqBadge.className = 'px-1.5 py-0.5 rounded bg-white/10 text-slate-300 font-mono font-bold text-[10px]';
            seqBadge.textContent = `#${seqNum}`;
            leftInfo.appendChild(seqBadge);

            const inningText = document.createElement('span');
            inningText.className = 'font-mono text-pitchcyan font-bold';
            inningText.textContent = `${ev.top ? '▲' : '▼'} Inn ${ev.inning}`;
            leftInfo.appendChild(inningText);

            const dot = document.createElement('span');
            dot.className = 'text-white/20';
            dot.textContent = '•';
            leftInfo.appendChild(dot);

            const countText = document.createElement('span');
            countText.className = 'font-mono text-slate-300';
            countText.textContent = `Count ${ev.balls}-${ev.strikes}`;
            leftInfo.appendChild(countText);

            headerRow.appendChild(leftInfo);

            const badge = document.createElement('span');
            const k = ev.kind;
            if (k === 'strike') {
                if (ev.strikes === 2) {
                    badge.className = 'px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40 text-[10px] font-mono font-bold';
                    badge.textContent = 'STRIKEOUT (K)';
                } else {
                    badge.className = 'px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-mono font-bold';
                    badge.textContent = 'STRIKE';
                }
            } else if (k === 'ball') {
                if (ev.balls === 3) {
                    badge.className = 'px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-mono font-bold';
                    badge.textContent = 'WALK (BB)';
                } else {
                    badge.className = 'px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono font-bold';
                    badge.textContent = 'BALL';
                }
            } else if (k === 'foul') {
                badge.className = 'px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'FOUL';
            } else if (k === 'hbp') {
                badge.className = 'px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'HIT BY PITCH';
            } else if (k === 'in_play') {
                badge.className = 'px-2 py-0.5 rounded-full bg-pitchcyan/20 text-pitchcyan border border-pitchcyan/30 text-[10px] font-mono font-bold';
                badge.textContent = 'IN PLAY';
            } else if (k === 'single') {
                badge.className = 'px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'SINGLE (1B)';
            } else if (k === 'double') {
                badge.className = 'px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'DOUBLE (2B)';
            } else if (k === 'triple') {
                badge.className = 'px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'TRIPLE (3B)';
            } else if (k === 'home_run') {
                badge.className = 'px-2 py-0.5 rounded-full bg-purple-500/30 text-purple-300 border border-purple-500/50 text-[10px] font-mono font-black animate-pulse';
                badge.textContent = 'HOME RUN (HR)';
            } else if (k === 'out') {
                badge.className = 'px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'OUT';
            } else if (k === 'error') {
                badge.className = 'px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'ERROR (E)';
            } else if (k === 'sac_fly') {
                badge.className = 'px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono font-bold';
                badge.textContent = 'SAC FLY';
            } else if (k === 'double_play') {
                badge.className = 'px-2 py-0.5 rounded-full bg-rose-500/30 text-rose-300 border border-rose-500/50 text-[10px] font-mono font-black';
                badge.textContent = 'DOUBLE PLAY';
            } else {
                badge.className = 'px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono';
                badge.textContent = k.toUpperCase();
            }
            headerRow.appendChild(badge);
            card.appendChild(headerRow);

            const narrativeRow = document.createElement('div');
            narrativeRow.className = 'text-xs text-slate-200 flex items-center justify-between';

            const descSpan = document.createElement('span');
            const veloText = ev.mph !== undefined && ev.mph !== null ? ` [${ev.mph} mph]` : '';
            let narrative = `${pName} to ${bName}: ${k.replace('_', ' ').toUpperCase()}${veloText}`;
            if (k === 'strike') {
                narrative = `${pName} delivers strike to ${bName}${veloText}`;
            } else if (k === 'ball') {
                narrative = `${pName} misses outside to ${bName}${veloText}`;
            } else if (k === 'foul') {
                narrative = `${bName} fouls it off into the stands${veloText}`;
            } else if (k === 'in_play') {
                narrative = `${bName} puts ball in play against ${pName}${veloText}`;
            } else if (k === 'single') {
                narrative = `${bName} lines a single into shallow field`;
            } else if (k === 'double') {
                narrative = `${bName} drills an extra-base double into the gap`;
            } else if (k === 'triple') {
                narrative = `${bName} races to 3rd for a standup triple!`;
            } else if (k === 'home_run') {
                narrative = `DEEP FLY TO THE STANDS! ${bName} clears the fence for a HOME RUN!`;
            } else if (k === 'out') {
                narrative = `${bName} grounds/flies out to retire the play`;
            } else if (k === 'double_play') {
                narrative = `Twin killing! Defense turns a 2-out double play`;
            } else if (k === 'error') {
                narrative = `Fielding miscue allows ${bName} to reach safely on error`;
            } else if (k === 'sac_fly') {
                narrative = `Sacrifice fly scores runner from 3rd base`;
            }
            descSpan.textContent = narrative;
            narrativeRow.appendChild(descSpan);
            card.appendChild(narrativeRow);

            scoreBallByBallFeed.appendChild(card);
        });
    }

    if (pitcherNameInput) {
        pitcherNameInput.addEventListener('input', () => {
            if (scoreCurrentState) scoreRenderBallByBall(scoreCurrentState);
        });
    }
    if (batterNameInput) {
        batterNameInput.addEventListener('input', () => {
            if (scoreCurrentState) scoreRenderBallByBall(scoreCurrentState);
        });
    }

    // Phase C: Offer pitch result in #scoreConfirm
    function scoreOfferConfirm(data) {
        if (!data || !scoreCurrentGameId || !scoreCurrentState) {
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            return;
        }

        // Rule 1: Offer only when pitch_detected === true, zone_calibrated === true and call is STRIKE or BALL.
        // For SET ZONE, NO PITCH DETECTED or normal mode: do not auto-suggest.
        if (activeTrackingMode === 'normal' || (data.mode && data.mode === 'normal')) {
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            return;
        }
        if (data.pitch_detected !== true || data.zone_calibrated !== true) {
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            return;
        }
        if (data.call !== 'STRIKE' && data.call !== 'BALL') {
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            return;
        }

        // Rule 3: No double counting - remember last data.video_id added
        if (data.video_id && data.video_id === scoreLastAddedVideoId) {
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            return;
        }

        const mph = typeof data.velocity_mph === 'number' ? Math.round(data.velocity_mph * 10) / 10 : null;
        scorePendingPitch = {
            call: data.call,
            mph: mph,
            video_id: data.video_id || null
        };

        const confirmButtons = [scoreConfirmAdd, scoreConfirmFoul, scoreConfirmInPlay, scoreConfirmHbp, scoreConfirmSkip];

        // Rule 5: If the game is over or awaiting_play, show the bar disabled with the reason
        if (scoreCurrentState.over) {
            if (scoreConfirmText) scoreConfirmText.textContent = "Game Over: Pitch not added";
            confirmButtons.forEach(btn => { if (btn) btn.disabled = true; });
            if (scoreConfirm) scoreConfirm.classList.remove('hidden');
            return;
        }

        if (scoreCurrentState.awaiting_play) {
            if (scoreConfirmText) scoreConfirmText.textContent = "Resolve ball in play before next pitch";
            confirmButtons.forEach(btn => { if (btn) btn.disabled = true; });
            if (scoreConfirm) scoreConfirm.classList.remove('hidden');
            return;
        }

        confirmButtons.forEach(btn => { if (btn) btn.disabled = false; });
        const mphStr = mph !== null ? `, ${mph.toFixed(1)} mph` : '';
        if (scoreConfirmText) scoreConfirmText.textContent = `Pitch: ${data.call}${mphStr}`;
        if (scoreConfirm) scoreConfirm.classList.remove('hidden');
    }
    window.scoreOfferConfirm = scoreOfferConfirm;

    // Event listeners
    if (scoreStartBtn) {
        scoreStartBtn.addEventListener('click', async () => {
            const away = (scoreAway && scoreAway.value.trim()) || 'Away';
            const home = (scoreHome && scoreHome.value.trim()) || 'Home';
            const innings = parseInt(scoreInnings && scoreInnings.value, 10) || 9;
            scoreLastAddedVideoId = null;
            scorePendingPitch = null;
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            try {
                await scoreCall('/api/games', { away, home, innings });
            } catch (e) {}
        });
    }

    if (scoreNewBtn) {
        scoreNewBtn.addEventListener('click', () => {
            scoreSetStoredId(null);
            scoreCurrentGameId = null;
            scoreLastAddedVideoId = null;
            scorePendingPitch = null;
            scoreHideError();
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            scoreRender(null);
        });
    }

    // Confirm bar actions
    if (scoreConfirmAdd) {
        scoreConfirmAdd.addEventListener('click', async () => {
            if (!scorePendingPitch || !scoreCurrentGameId) return;
            const payload = {
                kind: scorePendingPitch.call.toLowerCase(),
                source: "abs"
            };
            if (scorePendingPitch.mph !== null) payload.mph = scorePendingPitch.mph;
            scoreLastAddedVideoId = scorePendingPitch.video_id;
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/pitch`, payload);
            } catch (e) {}
        });
    }

    if (scoreConfirmFoul) {
        scoreConfirmFoul.addEventListener('click', async () => {
            if (!scorePendingPitch || !scoreCurrentGameId) return;
            const payload = { kind: "foul", source: "manual" };
            if (scorePendingPitch.mph !== null) payload.mph = scorePendingPitch.mph;
            scoreLastAddedVideoId = scorePendingPitch.video_id;
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/pitch`, payload);
            } catch (e) {}
        });
    }

    if (scoreConfirmInPlay) {
        scoreConfirmInPlay.addEventListener('click', async () => {
            if (!scorePendingPitch || !scoreCurrentGameId) return;
            const payload = { kind: "in_play", source: "manual" };
            if (scorePendingPitch.mph !== null) payload.mph = scorePendingPitch.mph;
            scoreLastAddedVideoId = scorePendingPitch.video_id;
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/pitch`, payload);
            } catch (e) {}
        });
    }

    if (scoreConfirmHbp) {
        scoreConfirmHbp.addEventListener('click', async () => {
            if (!scorePendingPitch || !scoreCurrentGameId) return;
            const payload = { kind: "hbp", source: "manual" };
            if (scorePendingPitch.mph !== null) payload.mph = scorePendingPitch.mph;
            scoreLastAddedVideoId = scorePendingPitch.video_id;
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/pitch`, payload);
            } catch (e) {}
        });
    }

    if (scoreConfirmSkip) {
        scoreConfirmSkip.addEventListener('click', () => {
            if (scorePendingPitch) {
                scoreLastAddedVideoId = scorePendingPitch.video_id;
            }
            if (scoreConfirm) scoreConfirm.classList.add('hidden');
        });
    }

    scorePitchButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!scoreCurrentGameId) return;
            const kind = btn.getAttribute('data-pitch');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/pitch`, { kind, source: 'manual' });
            } catch (e) {}
        });
    });

    scorePlayButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!scoreCurrentGameId) return;
            const outcome = btn.getAttribute('data-play');
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/play`, { outcome });
            } catch (e) {}
        });
    });

    if (scoreAdjustBtn) {
        scoreAdjustBtn.addEventListener('click', () => {
            if (!scoreAdjust) return;
            scoreAdjust.classList.toggle('hidden');
            if (scoreRunsPlus) scoreRunsPlus.value = '0';
            if (scoreOutsPlus) scoreOutsPlus.value = '0';
        });
    }

    scoreBaseButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const nowActive = btn.dataset.active !== 'true';
            btn.dataset.active = nowActive ? 'true' : 'false';
            if (nowActive) {
                btn.classList.add('bg-pitchcyan', 'text-black', 'border-pitchcyan');
                btn.classList.remove('bg-slate-800', 'text-slate-300', 'border-white/10');
            } else {
                btn.classList.remove('bg-pitchcyan', 'text-black', 'border-pitchcyan');
                btn.classList.add('bg-slate-800', 'text-slate-300', 'border-white/10');
            }
        });
    });

    if (scoreAdjustApply) {
        scoreAdjustApply.addEventListener('click', async () => {
            if (!scoreCurrentGameId) return;
            const b = [false, false, false];
            scoreBaseButtons.forEach((btn, idx) => {
                if (btn.dataset.active === 'true' && idx >= 0 && idx < 3) {
                    b[idx] = true;
                }
            });
            const runs = parseInt(scoreRunsPlus && scoreRunsPlus.value, 10) || 0;
            const outs = parseInt(scoreOutsPlus && scoreOutsPlus.value, 10) || 0;
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/adjust`, { bases: b, runs, outs });
                if (scoreAdjust) scoreAdjust.classList.add('hidden');
                if (scoreRunsPlus) scoreRunsPlus.value = '0';
                if (scoreOutsPlus) scoreOutsPlus.value = '0';
            } catch (e) {}
        });
    }

    if (scoreUndoBtn) {
        scoreUndoBtn.addEventListener('click', async () => {
            if (!scoreCurrentGameId) return;
            try {
                await scoreCall(`/api/games/${scoreCurrentGameId}/undo`, {});
            } catch (e) {}
        });
    }

    if (scoreLogToggle) {
        scoreLogToggle.addEventListener('click', () => {
            if (scoreLog) scoreLog.classList.toggle('hidden');
        });
    }

    // On page load: check localStorage for saved game id
    function scoreInit() {
        const savedId = scoreGetStoredId();
        if (savedId) {
            scoreCurrentGameId = savedId;
            scoreCall(`/api/games/${savedId}`).catch(() => {
                scoreSetStoredId(null);
                scoreCurrentGameId = null;
                scoreRender(null);
            });
        } else {
            scoreRender(null);
        }
    }
    scoreInit();
});

