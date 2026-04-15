# Verus Proof Synthesis

<p align="left">
    <a href="https://arxiv.org/abs/2409.13082"><img src="https://img.shields.io/badge/AutoVerus-arXiv%202409.13082-b31b1b.svg?style=for-the-badge"></a>
    <a href="https://arxiv.org/abs/2512.18436"><img src="https://img.shields.io/badge/VeruSAGE-arXiv%202512.18436-b31b1b.svg?style=for-the-badge"></a>
    <a href="https://www.microsoft.com/en-us/research/project/practical-system-verification/"><img src="https://img.shields.io/badge/Website-blue.svg?style=for-the-badge"></a>
    <a href="https://microsoft.github.io/verus-proof-synthesis/"><img src="https://img.shields.io/badge/🏆_Leaderboard-View_Results-6366f1.svg?style=for-the-badge"></a>
</p>

This repository contains tools and benchmarks for automated [Verus](https://github.com/verus-lang/verus) proof synthesis. The main addition for interactive, verifier-guided repair is **`verus_solver`**; the upstream research systems **AutoVerus** and **VeruSAGE** and their benchmarks live alongside it.

> **[Leaderboard](leaderboard)** — Compare systems on the published benchmarks.

---

## Verifier-guided solver (`verus_solver`)

A standalone Python CLI that loops on **Verus output**: it triages errors, applies deterministic repair strategies, rotates strategies when progress stalls, and optionally calls an LLM for patches. See **[verus_solver/README.md](verus_solver/README.md)** for install, config, and commands.

```bash
pip install -r requirements.txt
cp verus_solver/config.local.example.yaml verus_solver/config.local.yaml
# Edit verus_solver/config.local.yaml: set verus_path, optional OPENAI_API_KEY for LLM fallback

python3 -m verus_solver.cli solve path/to/file.rs --out path/to/out.rs --config verus_solver/config.local.yaml
```

**Config notes**

- Point `verus_path` at a Verus binary (official release builds work well).
- Set `OPENAI_API_KEY` in your environment if `use_llm_fallback: true`.

---

## AutoVerus (upstream)

**AutoVerus** is a three-phase LLM pipeline (inference → refinement → repair) for small algorithmic Verus programs. Implementation and few-shot examples are under **`autoverus/`**.

```bash
cd autoverus
python3 main.py --config config.json --input examples/input-condinv/ex1.rs --output /tmp/out.rs
```

Details: **[autoverus/README.md](autoverus/README.md)**.  
Artifact reproduction: **[README-artifact-evaluation.md](README-artifact-evaluation.md)**.

---

## VeruSAGE (upstream)

**VeruSAGE** targets larger systems-style verification with an agent loop. Code is under **`verusage/`**.

```bash
cd verusage
python3 main.py --config config.json --input your_file.rs --output repaired_file.rs
```

Details: **[verusage/README.md](verusage/README.md)**.

---

## Benchmarks

| Suite | Size | README |
|-------|------|--------|
| Verus-Bench | 150 algorithmic tasks | [benchmarks/Verus-Bench/README.md](benchmarks/Verus-Bench/README.md) |
| VeruSAGE-Bench | 849 systems tasks | [benchmarks/VeruSAGE-Bench/README.md](benchmarks/VeruSAGE-Bench/README.md) |

---

## Installation (shared)

### Docker

```bash
docker build -t verus-proof-synthesis .
docker run -it verus-proof-synthesis
```

### Local prerequisites

- Python 3.10+
- A [Verus](https://github.com/verus-lang/verus) binary (build from source or use a [release](https://github.com/verus-lang/verus/releases))
- For LLM-based tools: `OPENAI_API_KEY` (or Azure config where documented in each subproject)

**Building Verus from source** (abbreviated; see upstream `BUILD.md`):

```bash
git clone https://github.com/verus-lang/verus.git
cd verus/source
./tools/get-z3.sh && source ../tools/activate
vargo build --release
# Binary typically at: verus/source/target-verus/release/verus
```

---

## Repository layout

```
verus-proof-synthesis/
├── verus_solver/       # Verifier-guided solver (CLI, strategies, bench harness)
├── autoverus/          # AutoVerus: inference / refinement / repair
├── verusage/           # VeruSAGE: agentic repair
├── benchmarks/         # Verus-Bench, VeruSAGE-Bench
├── utils/              # Shared helpers (e.g. Lynette parser)
├── my_inputs/          # Local example inputs (optional)
└── generated/          # Pre-generated / experiment outputs
```

---

## Further reading

- AutoVerus: [arXiv:2409.13082](https://arxiv.org/abs/2409.13082)
- VeruSAGE: [arXiv:2512.18436](https://arxiv.org/abs/2512.18436)
- Verus guide: [verus-lang.github.io/verus/guide](https://verus-lang.github.io/verus/guide/)

---

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repositories using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow Microsoft's Trademark & Brand Guidelines. Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.

---

## Citation

If you find this work useful, please consider citing:

```bibtex
@article{autoverus,
  title={AutoVerus: Automated Proof Generation for Rust Code},
  author={Chenyuan Yang and Xuheng Li and Md Rakib Hossain Misu and Jianan Yao and Weidong Cui and Yeyun Gong and Chris Hawblitzel and Shuvendu K. Lahiri and Jacob R. Lorch and Shuai Lu and Fan Yang and Ziqiao Zhou and Shan Lu},
  journal={Proceedings of the ACM on Programming Languages},
  volume={9},
  number={OOPSLA2},
  year={2025},
  publisher={ACM New York, NY, USA}
}

@misc{verusage,
  title={VeruSAGE: A Study of Agent-Based Verification for Rust Systems},
  author={Chenyuan Yang and Natalie Neamtu and Chris Hawblitzel and Jacob R. Lorch and Shan Lu},
  year={2025},
  eprint={2512.18436},
  archivePrefix={arXiv},
  primaryClass={cs.OS},
  url={https://arxiv.org/abs/2512.18436},
}
```
