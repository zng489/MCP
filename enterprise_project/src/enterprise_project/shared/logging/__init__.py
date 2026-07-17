"""
    Simple logging module for the enterprise project.

    Exemplo prático:

Imagine sua pasta logging tem VÁRIOS arquivos internos:

logging/
├── __init__.py
├── logger.py          (implementação da função get_logger)
├── handlers.py        (funções internas para handlers)
├── formatters.py      (funções internas para formatters)
└── utils.py           (funções utilitárias internas)
SEM o __init__.py proper:

# Usuário poderia fazer isso (e TUDO fica público):
from enterprise_project.shared.logging.logger import get_logger  ✅
from enterprise_project.shared.logging.handlers import _internal_handler  ✅ Oops!
from enterprise_project.shared.logging.utils import _private_util  ✅ Oops!

Você NÃO quer que users acessem _internal_handler e _private_util!

# __init__.py
from .logger import get_logger
__all__ = ["get_logger"]  # "Só isso é público!"

# Usuário pode fazer:
from enterprise_project.shared.logging import get_logger  ✅ Permitido

# Usuário NÃO deveria fazer (não é documentado):
from enterprise_project.shared.logging.utils import _private_util  ❌ Técnico possível, mas não incentivado

# logger.py (implementação)
def get_logger(name, log_file=None, level=logging.INFO):
    Cria um logger

def setup_logging(log_level="INFO", log_file=None, log_dir=None):
    Configura logging global

def reset_logger(name):
    Reseta um logger específico


from .logger import get_logger, setup_logging, reset_logger
__all__ = [
    "get_logger",
    "setup_logging", 
    "reset_logger"
]
"""

from .logger import get_logger

__all__ = ["get_logger"]

