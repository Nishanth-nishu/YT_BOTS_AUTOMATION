# Running AnimeForge GPU work on the Ada cluster

The laptop has no NVIDIA GPU. GPU work runs as Slurm jobs on Ada's `plafnet2`
partition (RTX 3090, 24 GB), driven from the laptop over `ssh ada`.

## Storage rules (learned the hard way)

| Place | What it is | Use it for |
|---|---|---|
| `/scratch/$USER/animeforge` | Local to one compute node. **Purged after about 7 days.** | Environments, model cache, work in progress |
| `/share6/$USER/animeforge/hf` | Persistent, 100 GB and 10,000-file quota. **Mounted only on the gateway.** | The saved copy of every model |
| `~/animeforge` | Home, about 5 GB free | Source, logs, small results |

- Jobs reach share6 over SSH to the gateway as `ada-gw1` (`models_sync.sh`):
  `af_restore` at the start copies in any model missing on the node,
  `af_backup` after downloads copies new models out. The backup checks the
  quota first and refuses if it would leave under 2 GB.
- Python environments are never saved (tens of thousands of files); `setup_env.sh`
  and `setup_tts.sh` rebuild them on any node in about 10 to 15 minutes.
- Each job copies the source to scratch before running. Uploading new source
  while a job read it from home caused a "Stale file handle" failure.
- Jobs run on any plafnet2 node except gnode118. An episode copies its finished
  shots home, so a retry on another node does not redo them.

## Jobs

| Script | What it does | Measured |
|---|---|---|
| `first_shot.sbatch` | Four Arjuna stills, then one 5 s clip | 17.5 min clip at 50 steps |
| `bench_video.sbatch` | Same clip at cheaper settings | see the registry benchmark |
| `consistency.sbatch` | Six scenes with and without IP-Adapter Plus | 92 s for 12 images |
| `voice.sbatch` | Hindi lines with Chatterbox, checked by Whisper | see `docs/animeforge/ROADMAP.md` |
| `lipsync.sbatch` | Audio-timed lip flaps for one line | see the roadmap |
| `shot.sbatch` | One still and one clip for the job queue (`SHOT_ID`, prompts in `prompts/`) | not run yet |
| `episode.sbatch` | Stills, clips and voices for every shot of an episode (`EPISODE_ID`) | about 11.4 min a clip at 30 steps |
| `lora_set.sbatch` | 64 candidate pictures of an episode's character, and the training environment | 9 min |
| `lora_train.sbatch` | Kohya LoRA on the pictures listed in `selected.txt`, then a six-scene test (`TRIGGER`) | 25 min training |
| `lora_eval.sbatch` | The six-scene test at other LoRA weights (`SCALES`) | 8 min |
| `backup.sbatch` | Save the model cache to share6 (no GPU) | 39 GB in 6 min |

## From the laptop

    python -m animeforge.episode check <id>      # rules, rights, licences
    python -m animeforge.episode produce <id>    # submit, wait, fetch, cut, QA
    python -m animeforge.episode fetch <id>      # fetch and cut a job that already ran
    python -m animeforge.jobs work               # run queued jobs (API: python -m animeforge.api)

## Failures met so far, and the fix in the code

| Failure | Cause | Fix |
|---|---|---|
| Out of memory at the end of a clip | Decoding 121 frames at 704x1280 in one piece | Tiled VAE decode |
| Out of memory with no offload | Text encoder, transformer and VAE together exceed 24 GB | Model CPU offload |
| `Stale file handle` | Source replaced over NFS during a job | Private source copy per job |
| Voice job timed out | Chatterbox downloads a Chinese segmenter from GitHub at start-up | Retried |
| `PerthImplicitWatermarker` is `None` | The watermark library needs `pkg_resources` | `setuptools<81` in the TTS environment |
| Jobs waiting a day | Pinned to one busy node | Any node, models restored from share6 |
| Voice job hit its 90-minute limit | Package downloads on gnode116 crawled (normally about 10 minutes) | 3-hour limit; rerun |
| `A virtual environment already exists` | Two jobs started together on one node and both built the environment | `flock` in both setup scripts |
| Selective restore copied only links | The model cache keeps weights in `hub/blobs`; model folders hold links | Restore list = the model folder plus the blobs its links name |
| Clips lost when a later step failed | Results were copied home only at the end | Episode job copies its output home on any exit |
| LoRA training stopped in 17 s | With fp16 the trainer wants fp16-variant files the base model lacks | `--mixed_precision bf16` |
| A voice line ran on into nonsense | The speech model did not stop at the end of the sentence | Every take is transcribed; bad ones are retaken |

## Character LoRA, step by step

1. `lora_set.sbatch` with `EPISODE_ID`: pictures land in `~/animeforge/out/lora-<id>/` with numbered contact sheets.
2. Look at the sheets; write the numbers to keep (12 or more) into `selected.txt` in that folder.
3. `lora_train.sbatch` with `EPISODE_ID` and `TRIGGER`: files land in `~/animeforge/loras/` and on share6.
4. Look at `eval/contact_sheet.jpg` (rows: text, adapter, LoRA, LoRA with adapter); try other weights with `lora_eval.sbatch`.
5. In the episode file set `lora`, `lora_scale`, `lora_trigger`, and `reference_scale` 0.
