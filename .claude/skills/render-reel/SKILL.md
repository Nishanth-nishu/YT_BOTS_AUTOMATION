---
name: render-reel
description: Render a REELFORGE ReelSpec to MP4 with the Remotion Reel composition, locally (CPU, draft or standard) or on the Ada cluster (RTX 3090, NVENC), then post-encode to Instagram-safe H.264 and record a benchmark. Use when the user says "render the reel", "export", "give me the MP4", "render on Ada".
---

# render-reel

## Purpose
Produce the MP4 (and cover PNG) for a timed spec, with resource measurements.

## Trigger
`data/storyboards/<id>.timed.json` exists and the Remotion code type-checks (`cd video-engine && npx tsc --noEmit`).

## Inputs
- Timed spec path, profile (`draft` 720x1280, `standard` or `cinematic` 1080x1920), target (`local` or `ada`).

## Outputs
- `output/drafts/<id>.<profile>.mp4` (yuv420p, bt709 tv range, AAC 192k, faststart).
- `output/covers/<id>.png` (from the `Cover` still).
- `output/reports/<id>.<profile>.benchmark.json` (render seconds, encode seconds, peak RSS, CPU).

## Workflow (local)
```bash
.venv\Scripts\python -m services.rendering.local_render --spec data/storyboards/<id>.timed.json --profile draft --concurrency 2
cd video-engine && npx remotion still src/index.ts Cover ../output/covers/<id>.png --props=<cover props json>
```
Check free RAM first (`Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory`). Below about 2.5 GB free, use `--concurrency 1` or render on Ada.

## Workflow (Ada)
1. Sync: `tar czf - --exclude=node_modules --exclude=out video-engine infra | ssh ada 'tar xzf - -C ~/reelforge'` and copy the props file into `~/reelforge/runs/<id>/`.
2. Submit: `ssh ada 'cd ~/reelforge && sbatch --export=ALL,COMP=Reel,PROPS=runs/<id>/props.json,OUT=runs/<id>/<id>.mp4,PROFILE=standard infra/ada/render_job.sh'`.
3. Poll `squeue -u $USER`; read `~/reelforge/logs/render_<job>.log` for `RENDER_SECONDS`, `PEAK_RSS_MB`, `JOB_OK`.
4. Fetch: `scp ada:~/reelforge/runs/<id>/<id>.mp4 output/drafts/`.
Never pass `--nodelist=gnode118`; the job template excludes it.

## Validation
Run `review-reel` on the output. Do not call a render done until ffprobe passes and frames were inspected.

## Error handling
- Chrome download failure: `npx remotion browser ensure` (needs internet once).
- `Old Headless mode has been removed`: Remotion's bundled headless shell avoids this; do not pass `--browser-executable`.
- Out of memory locally: lower concurrency, use draft, or go to Ada.
- Ada `ECONNRESET` during npm: re-run `infra/ada/bootstrap.sh` (retries are configured).

## Dependencies
Node 24 local / Node 22 on Ada, Remotion 4.0.540, FFmpeg 9 local / 7.1.1 module on Ada, psutil.
