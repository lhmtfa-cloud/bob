from enum import Enum
from typing import Dict
from threading import Lock

class ProcessingStage(str, Enum):
    RECEIVED = "received"
    UPLOADING = "uploading"
    QA_PROCESSING = "question_answering"
    SUMMARIZING = "summarizing"
    GENERATING_PDF = "generating_pdf"
    FINISHED = "finished"
    ZIPPING = "zipping"
    ERROR = "error"

state_lock = Lock()
processing_states: Dict[str, str] = {}

def set_processing_state(code: str, stage: ProcessingStage):
    with state_lock:
        processing_states[code] = stage.value

def get_processing_state(code: str) -> str:
    with state_lock:
        return processing_states.get(code, "not_found")