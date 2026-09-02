from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from material_platform.domain.enums import MaterialType
from material_platform.eval.cases import (
    SEMANTIC,
    EvalCase,
    EvalSuite,
    ExpectedHit,
)

Kind = Literal[
    "pdf",
    "md",
    "md_as_docx",
    "alpaca_json",
    "github_zip",
    "pypi_wheel",
    "jar",
    "npm_tgz",
]

_REPO = Path(__file__).resolve().parents[3]
AIML_DIR = _REPO / "tests" / "fixtures" / "eval_aiml"
AIML_CACHE = AIML_DIR / "cache"
AIML_ZIP = AIML_DIR / "research.zip"
AIML_GENERATED_SUITE = AIML_DIR / "eval_aiml.json"

SLP3_PDF = "slp3.pdf"
FOUNDATION_PDF = "foundation_models.pdf"
QLORA_PDF = "qlora.pdf"
REACT_PDF = "react.pdf"
LORA_PDF = "lora.pdf"
LLM_SURVEY_PDF = "llm_survey.pdf"
INSTRUCTGPT_PDF = "instructgpt.pdf"
PEFT_DOCX = "peft_trl.docx"
REACT_MD = "react_readme.md"
ALPACA_CSV = "alpaca_sft.csv"
TRANSFORMERS_ROOT = "labs/transformers/"
PEFT_ROOT = "labs/peft/"
TRANSFORMERS_JS_ROOT = "apps/transformers_js/"
DATA_ROOT = "data/"
PACKAGES_ROOT = "packages/"

# Distinctive phrases that should appear in the downloaded files.
# Pytest e2e (EVAL_AIML=1) requires these lexical ids; the rest are probes.
REQUIRED_LEXICAL_IDS = frozenset(
    {
        "slp3-title",
        "qlora-nf4",
        "alpaca-instruction",
        "djl-jar",
    }
)


@dataclass(frozen=True)
class RemoteFile:
    url: str
    dest: str
    kind: Kind
    fallbacks: tuple[str, ...] = ()


# Public AI/ML sources. Ingest never hits the network; scripts/eval_aiml.py
# downloads these into a local zip first. SLP3 is class-use only — do not commit.
SOURCES: tuple[RemoteFile, ...] = (
    RemoteFile(
        "https://web.stanford.edu/~jurafsky/slp3/ed3book_aug26.pdf",
        f"papers/{SLP3_PDF}",
        "pdf",
        fallbacks=(
            "https://web.stanford.edu/~jurafsky/slp3/ed3book.pdf",
            "https://stanford.edu/~jurafsky/slp3/ed3book_aug26.pdf",
        ),
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2108.07258",
        f"papers/{FOUNDATION_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2303.18223",
        f"papers/{LLM_SURVEY_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2305.14314",
        f"papers/{QLORA_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2210.03629",
        f"papers/{REACT_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2106.09685",
        f"papers/{LORA_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://arxiv.org/pdf/2203.02155",
        f"papers/{INSTRUCTGPT_PDF}",
        "pdf",
    ),
    RemoteFile(
        "https://raw.githubusercontent.com/huggingface/trl/main/docs/source/peft_integration.md",
        f"papers/{PEFT_DOCX}",
        "md_as_docx",
    ),
    RemoteFile(
        "https://raw.githubusercontent.com/ysymyth/ReAct/master/README.md",
        f"notes/{REACT_MD}",
        "md",
    ),
    RemoteFile(
        "https://raw.githubusercontent.com/tatsu-lab/stanford_alpaca/main/alpaca_data.json",
        f"{DATA_ROOT}{ALPACA_CSV}",
        "alpaca_json",
    ),
    RemoteFile(
        "https://github.com/huggingface/transformers/archive/refs/tags/v4.45.2.zip",
        TRANSFORMERS_ROOT,
        "github_zip",
    ),
    RemoteFile(
        "https://github.com/huggingface/peft/archive/refs/tags/v0.13.2.zip",
        PEFT_ROOT,
        "github_zip",
    ),
    RemoteFile(
        "https://github.com/huggingface/transformers.js/archive/refs/tags/3.0.0.zip",
        TRANSFORMERS_JS_ROOT,
        "github_zip",
        fallbacks=(
            "https://github.com/huggingface/transformers.js/archive/refs/tags/2.17.2.zip",
        ),
    ),
    RemoteFile(
        "https://pypi.org/pypi/peft/json",
        PACKAGES_ROOT,
        "pypi_wheel",
    ),
    RemoteFile(
        "https://pypi.org/pypi/huggingface-hub/json",
        PACKAGES_ROOT,
        "pypi_wheel",
    ),
    RemoteFile(
        "https://repo1.maven.org/maven2/ai/djl/api/0.31.1/api-0.31.1.jar",
        f"{PACKAGES_ROOT}djl-api-0.31.1.jar",
        "jar",
    ),
    RemoteFile(
        "https://registry.npmjs.org/onnxruntime-web/-/onnxruntime-web-1.19.2.tgz",
        f"{TRANSFORMERS_JS_ROOT}node_modules/onnxruntime-web/",
        "npm_tgz",
    ),
)


def expected_roots() -> tuple[str, ...]:
    return (
        "README.md",
        f"papers/{SLP3_PDF}",
        f"papers/{FOUNDATION_PDF}",
        f"papers/{LLM_SURVEY_PDF}",
        f"papers/{QLORA_PDF}",
        f"papers/{REACT_PDF}",
        f"papers/{LORA_PDF}",
        f"papers/{INSTRUCTGPT_PDF}",
        f"papers/{PEFT_DOCX}",
        f"notes/{REACT_MD}",
        DATA_ROOT,
        TRANSFORMERS_ROOT,
        PEFT_ROOT,
        TRANSFORMERS_JS_ROOT,
        f"{PACKAGES_ROOT}djl-api-0.31.1.jar",
    )


def expected_type(root_path: str) -> MaterialType | None:
    mapping = {
        "README.md": MaterialType.DOCUMENT,
        f"papers/{SLP3_PDF}": MaterialType.DOCUMENT,
        f"papers/{FOUNDATION_PDF}": MaterialType.DOCUMENT,
        f"papers/{LLM_SURVEY_PDF}": MaterialType.DOCUMENT,
        f"papers/{QLORA_PDF}": MaterialType.DOCUMENT,
        f"papers/{REACT_PDF}": MaterialType.DOCUMENT,
        f"papers/{LORA_PDF}": MaterialType.DOCUMENT,
        f"papers/{INSTRUCTGPT_PDF}": MaterialType.DOCUMENT,
        f"papers/{PEFT_DOCX}": MaterialType.DOCUMENT,
        f"notes/{REACT_MD}": MaterialType.DOCUMENT,
        DATA_ROOT: MaterialType.DATASET,
        TRANSFORMERS_ROOT: MaterialType.PROJECT,
        PEFT_ROOT: MaterialType.PROJECT,
        TRANSFORMERS_JS_ROOT: MaterialType.PROJECT,
        f"{PACKAGES_ROOT}djl-api-0.31.1.jar": MaterialType.CODE,
    }
    if root_path in mapping:
        return mapping[root_path]
    if root_path.startswith(PACKAGES_ROOT) and root_path.endswith(".whl"):
        return MaterialType.CODE
    if root_path.startswith(PACKAGES_ROOT) and root_path.endswith(".jar"):
        return MaterialType.CODE
    return None


def make_suite() -> EvalSuite:
    return EvalSuite(
        id="eval_aiml",
        cases=(
            EvalCase(
                id="slp3-title",
                query="Speech and Language Processing",
                expect=(ExpectedHit(path=SLP3_PDF),),
            ),
            EvalCase(
                id="qlora-nf4",
                query="4-bit NormalFloat",
                expect=(ExpectedHit(path=QLORA_PDF),),
            ),
            EvalCase(
                id="react-paper",
                query="Synergizing Reasoning and Acting",
                expect=(ExpectedHit(path=REACT_PDF),),
            ),
            EvalCase(
                id="lora-paper",
                query="Low-Rank Adaptation of Large Language Models",
                expect=(ExpectedHit(path=LORA_PDF),),
            ),
            EvalCase(
                id="foundation-homogenization",
                query="homogenization",
                expect=(ExpectedHit(path=FOUNDATION_PDF),),
            ),
            EvalCase(
                id="peft-project",
                query="get_peft_model",
                expect=(ExpectedHit(path="src/peft"),),
            ),
            EvalCase(
                id="transformers-pretrained",
                query="PreTrainedModel",
                expect=(ExpectedHit(path="src/transformers"),),
            ),
            EvalCase(
                id="react-readme",
                query="ReAct Prompting",
                expect=(ExpectedHit(path=REACT_MD, lines=True),),
            ),
            EvalCase(
                id="alpaca-instruction",
                query="Give three tips for staying healthy",
                expect=(ExpectedHit(path=ALPACA_CSV),),
            ),
            EvalCase(
                id="djl-jar",
                query="ai.djl",
                expect=(ExpectedHit(path="djl-api-0.31.1.jar"),),
            ),
            EvalCase(
                id="qlora-paraphrase",
                query="finetune a quantized 4-bit language model with adapters",
                mode=SEMANTIC,
                expect=(ExpectedHit(path=QLORA_PDF),),
            ),
            EvalCase(
                id="react-paraphrase",
                query="language agent that reasons then calls tools in a loop",
                mode=SEMANTIC,
                expect=(ExpectedHit(path=REACT_PDF),),
            ),
        ),
    )


def agent_cases() -> tuple[EvalCase, ...]:
    return (
        EvalCase(
            id="agent-qlora",
            query="What is NF4 NormalFloat in QLoRA fine-tuning?",
            expect=(ExpectedHit(path=QLORA_PDF),),
        ),
        EvalCase(
            id="agent-peft",
            query="Where is get_peft_model defined?",
            expect=(ExpectedHit(path="src/peft"),),
        ),
    )


AIML_SUITE = make_suite()
