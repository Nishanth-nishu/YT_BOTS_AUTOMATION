# REELFORGE Environment Report

Generated: 2026-11-05 (verified by direct inspection, not assumed)
Inspected at approximately 20:15 UTC / 01:45 IST on 2026-11-05.

## Summary of findings

The brief assumed a local RTX 3090. Inspection shows the **local Windows machine has no NVIDIA GPU at all**, only Intel UHD Graphics 770. The RTX 3090 with 24 GB VRAM exists on the **Ada HPC cluster** (IIIT), on the `plafnet2` partition nodes gnode113 to gnode116, which the user has authorised for use. gnode118 is explicitly off limits.

REELFORGE is therefore a **hybrid local-first system**:

| Role | Machine |
|---|---|
| Orchestration, code, SQLite, dashboard, Remotion Studio preview | Local Windows 11 (HP Pro Tower 400 G9) |
| Draft renders at 720x1280 on CPU, libx264 final encode fallback | Local Windows 11 |
| GPU TTS (Kokoro on CUDA), full-quality Remotion renders, NVENC encoding | Ada `plafnet2` partition, gnode113 to gnode116 |

## 1. Local machine (Windows 11)

### Hardware

| Item | Value |
|---|---|
| Model | HP Pro Tower 400 G9 PCI Desktop PC |
| OS | Microsoft Windows 11 Pro, build 10.0.26200 |
| CPU | 13th Gen Intel Core i5-13500, 14 cores / 20 threads, 2.5 GHz base |
| RAM | 15.68 GB total. **Only 1.43 GB free at inspection time** (Opera, Claude, Edge WebView and Chrome consume most). Virtual memory 59.8 GB total, 21.3 GB free. |
| GPU | Intel UHD Graphics 770 (integrated), driver 32.0.101.7077, 2 GB shared. **No NVIDIA adapter present.** `nvidia-smi` is not installed. No CUDA toolkit. |
| Storage | One 954 GB SSD (ABSNE271024KP). C: 339.6 GB used, 221.6 GB free. I: and R: drives each 195.2 GB free. |

Implications:
- No local NVENC. `h264_nvenc` is listed by the local FFmpeg build but cannot run without an NVIDIA device. Local encodes use libx264.
- RAM is the binding constraint locally. Remotion renders must use low concurrency (1 to 2 browser tabs) and the DRAFT profile when other apps are open.
- Local Chrome exists, so Remotion can render on CPU locally.

### Software

| Tool | Status | Path / version |
|---|---|---|
| Node.js | Installed | v24.22.1 at C:\Program Files\nodejs\node.exe |
| npm | Installed | 11.19.1 |
| npx | Installed | bundled |
| Python | Installed | 3.11.9 (64-bit) at C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe. Also Python 3.14 via `py -3.14`. |
| pip packages of interest | Present | fastapi 0.162.0, pydantic 2.14.1, httpx 0.28.1, numpy 2.4.6, onnxruntime 1.20.1, torch 2.14.0+cpu (no CUDA), uvicorn 0.54.0, pytest 9.1.1 |
| Git | Installed | 2.55.0.windows.3 |
| FFmpeg | **Installed during Phase 1** via `winget install Gyan.FFmpeg` (free, gyan.dev full build) | 9.0.2 at C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin. Encoders verified: libx264, aac, libopus. New shells get it on PATH. |
| Chrome | Installed | C:\Program Files\Google\Chrome\Application\chrome.exe |
| Edge | Installed | C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe |
| OpenSSH client | Installed | OpenSSH_for_Windows_9.5p2 |
| winget | Installed | v1.29.380 |
| Claude Code | Running inside the Claude desktop app (Code tab). The `claude` CLI binary is not on PATH in child shells, so `claude plugin install` cannot be run from scripts; skills were installed into the project instead (see SKILLS_REGISTRY.md). |

### Claude Code plugins and skills found before this project

- Marketplace: `claude-plugins-official` (anthropics/claude-plugins-official), last updated 2026-11-04.
- User-level skills in `~/.claude/skills`: find-skills, graphify, ig-* (Instagram content skills: audit, caption, carousel, comment, dm, human, plan, profile, reel, reply, repurpose, story, viral), protocol-reverse-engineering, replica-* (app cloning pack), scholar-scout.
- The `ig-reel`, `ig-caption` and `ig-human` skills are directly relevant to script and caption generation and will be reused by the content pipeline.

## 2. Ada HPC cluster (authorised by user, 2026-11-05)

Access: `ssh ada` (host alias in ~/.ssh/config pointing at ada-gw1.iiit.ac.in, user nishanth.r, key ~/.ssh/ada_iiit_new). Key-based login verified working with `BatchMode=yes`. Port 22 reachable from this machine.

The public wiki is outdated. Observed reality:

| Item | Observed |
|---|---|
| Login node | ada-gw1.iiit.ac.in, Rocky Linux 9.8, glibc 2.34 |
| Compute nodes (plafnet2) | Ubuntu 22.04.5 LTS, glibc 2.35 |
| Home | /home2/nishanth.r, 50 GB quota, 38 GB used, 13 GB free |
| /share1 | 95 TB, 51 TB free |
| Node scratch | /scratch 1.8 TB (1.7 TB free), /ssd_scratch 1.8 TB. Files older than 7 to 10 days purged. |
| Accounts / QoS for this user | d4 (QoS d4), plafnet (QoS normal), plafnet2 (QoS plafnet2) |
| Partitions | u22 (77 nodes), u22-cpu (6), ihub (12), **plafnet2 (gnode113, 114, 115, 116, 118)**, rrc (gnode117) |
| plafnet2 node spec (gnode116 probed) | **NVIDIA GeForce RTX 3090, 24576 MiB VRAM**, driver 580.178.04. 48 CPUs, 251 GB RAM. gnode113 to 116 have 2 GPUs each, gnode118 has 4. |
| Modules | u22/ffmpeg/7.1.1 (**h264_nvenc, hevc_nvenc, av1_nvenc verified**), u22/singularity-ce/4.2.2, u22/python/3.12.4 and 3.12.15, u22/cuda/9.2 |
| Chrome headless dependencies | 9 of the common shared libraries (libnss3, libatk, libgbm, libxkbcommon, libasound) found in ldconfig on gnode116, so Remotion's bundled Chrome Headless Shell should run. |
| Node.js | Not installed system-wide. Will be installed as a user-local prebuilt tarball in /scratch. |
| Existing user jobs | Two jobs on plafnet2 at inspection (one running on gnode118, one pending). REELFORGE must never request gnode118 and must use `--exclude=gnode118`. |

Job policy for REELFORGE on Ada:
- Partition `plafnet2`, account `plafnet2`, always `--exclude=gnode118`.
- Interactive probes via `srun --immediate=120 --time=00:10:00`.
- Production renders via `sbatch` with `--gres=gpu:1 --cpus-per-task=8 --mem=32G`.
- Work directory `/scratch/nishanth.r/reelforge` on the compute node, synced from local with rsync over the `ada` host.
- Never store credentials in the repo. SSH keys stay in ~/.ssh.

## 3. Resource policy derived from inspection

| Job type | Local | Ada |
|---|---|---|
| Research, scripting, storyboard | Yes (Claude Code, Python) | No |
| TTS (Kokoro) | CPU fallback, slow | CUDA primary |
| Draft render 720x1280 | Yes, concurrency 1 | Yes |
| Standard / Cinematic render 1080x1920 | Possible but slow and RAM-limited | Primary, concurrency 8 to 16 |
| Final encode | libx264 | h264_nvenc p5 cq 20 |
| QA (ffprobe, contact sheets) | Yes | Yes |
| Dashboard | Yes | No |

Concurrency rule: one TTS job, one render, one post-processing job at a time locally. On Ada, one SLURM job per Reel.

## 4. Verification commands used

```powershell
Get-CimInstance Win32_Processor | Select Name, NumberOfCores, NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select Model, TotalPhysicalMemory
Get-CimInstance Win32_VideoController | Select Name, DriverVersion, AdapterRAM
Get-PSDrive -PSProvider FileSystem
node --version; npm --version; python --version; git --version
winget install --id Gyan.FFmpeg -e
ffmpeg -hide_banner -encoders | Select-String "nvenc|libx264|aac"
```

```bash
ssh -o BatchMode=yes ada 'sinfo -o "%P %a %l %D %N"; sacctmgr show assoc user=$USER'
ssh ada 'srun -p plafnet2 -A plafnet2 --exclude=gnode118 --gres=gpu:1 -c 2 --mem=4G --time=00:04:00 --immediate=120 bash -lc "nvidia-smi --query-gpu=name,memory.total --format=csv; module load u22/ffmpeg/7.1.1; ffmpeg -encoders | grep nvenc"'
```
