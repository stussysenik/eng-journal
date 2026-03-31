# Prompt Efficiency Report - 2025-10-01 to 2026-03-31

## Claude Code
- Total prompts: 16396
- Average length: 7743.7 chars
- Mega prompts: 7935
- Control prompts: 592 | Substantive prompts: 15804
- Duplicate prompt instances: 4313
- Substantive duplicate instances: 4082
- Top semantic tags: design (10143), plan (9798), build (9723), research (8232), debug (2906), test (2573), agents (1211), refactor (312)
- Directive signals: verification_first (1132), parallel_agents (481), step_by_step (287), system_directive (42), interview_before_action (30), implement_direct (20)

### What Worked
- Baseline active day: 3.76 projects, 94.61 threads, 1951.84 execution actions, 91.21 mega prompts
- implement_direct: 1 days / 20 prompts, 24.00 projects/day (+20.24), 16923.00 execution/day (+14971.16)
- interview_before_action: 4 days / 30 prompts, 14.75 projects/day (+10.99), 11826.25 execution/day (+9874.41)
- system_directive: 13 days / 42 prompts, 10.31 projects/day (+6.55), 7350.62 execution/day (+5398.78)
- parallel_agents: 33 days / 481 prompts, 7.12 projects/day (+3.36), 4726.88 execution/day (+2775.04)
- verification_first: 60 days / 1132 prompts, 4.75 projects/day (+0.99), 2765.87 execution/day (+814.03)
- step_by_step: 33 days / 287 prompts, 3.00 projects/day (-0.76), 1839.52 execution/day (-112.32)

### Highest-Output Prompt Days
- 2026-03-21: 7283 prompts, 17 projects, 18327 execution actions, top projects tag-calibration, autoresearch-playground, redwood-rewrite-clean-writer, signals interview_before_action (8), parallel_agents (131), step_by_step (23), system_directive (6), verification_first (95)
- 2026-03-29: 629 prompts, 24 projects, 16923 execution actions, top projects portfolio-forever, windmill-portfolio, redwood-mymind-clone-web, signals implement_direct (20), interview_before_action (16), parallel_agents (18), system_directive (2), verification_first (26)
- 2026-03-23: 527 prompts, 6 projects, 11199 execution actions, top projects mit-ocw-reels, research, autoresearch-playground, signals parallel_agents (51), step_by_step (3), verification_first (119)
- 2026-03-13: 459 prompts, 16 projects, 10646 execution actions, top projects s3nik, mermaid-cli-claude-code-plan, common-lisp-koan, signals parallel_agents (15), system_directive (11), verification_first (71)
- 2026-03-22: 586 prompts, 9 projects, 10229 execution actions, top projects bboy-battle-analysis, redwood-mymind-clone-web, mit-ocw-reels, signals parallel_agents (102), step_by_step (3), verification_first (83)
- 2026-03-14: 421 prompts, 16 projects, 9513 execution actions, top projects trello-clone-swift-ui, autoresearch-playground, copy-paste-iphone, signals parallel_agents (12), step_by_step (1), system_directive (6), verification_first (73)
- 2026-03-31: 377 prompts, 10 projects, 8742 execution actions, top projects portfolio-forever, s3nik, Perplexica, signals interview_before_action (5), parallel_agents (12), verification_first (17)
- 2026-03-18: 321 prompts, 9 projects, 8404 execution actions, top projects mymind-clone-web, breakdex-flutter, MusicBrowser, signals parallel_agents (21), system_directive (3), verification_first (65)
- 2026-03-24: 344 prompts, 6 projects, 8268 execution actions, top projects breakdex-flutter, mit-ocw-reels, autoresearch-playground, signals parallel_agents (9), system_directive (1), verification_first (19)
- 2026-03-07: 317 prompts, 9 projects, 7867 execution actions, top projects breakdex-flutter, mymind-clone-web, onlook-ruby-elixir-clone, signals parallel_agents (13), verification_first (54)

### Repeated prompts
- 24x /usage
- 20x yes
- 19x /openspec:apply
- 17x /rate-limit-options
- 14x /openspec:proposal
- 11x Let's do it
- 10x /mcp
- 10x hi
- 10x /model
- 9x here you go

### Longest prompts
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [491764 chars]: You are a systems architect specializing in real-time ML inference pipelines, edge computing, and low-latency video processing. You are designing the production architecture for a breakdancing batt...
- bboy-battle-analysis [317821 chars]: You are a breakdancing technical analyst and movement scientist. You have deep knowledge of b-boy/b-girl culture, competition rules, and biomechanics. You are creating the formal move taxonomy and ...
- bboy-battle-analysis [317821 chars]: You are a breakdancing technical analyst and movement scientist. You have deep knowledge of b-boy/b-girl culture, competition rules, and biomechanics. You are creating the formal move taxonomy and ...
- bboy-battle-analysis [317821 chars]: You are a breakdancing technical analyst and movement scientist. You have deep knowledge of b-boy/b-girl culture, competition rules, and biomechanics. You are creating the formal move taxonomy and ...
- breakdex-flutter [298448 chars]: Showing Recent Issues Build target Runner of project Runner with configuration Debug warning: Run script build phase 'Re-sign Native Asset Frameworks' will be run during every build because it does...
