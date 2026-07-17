import logging
from pathlib import Path

# Essa linha define ONDE os arquivos de log serão salvos
# 
# Pense assim: você está em uma pasta bem funda dentro de várias pastas.
# A linha tira você de lá e coloca na pasta "logs" lá no topo.
#
# Visualização:
#   Você começa aqui:
#   C:\...\enterprise_project\src\enterprise_project\shared\logging\logger.py
#
#   E vai para aqui:
#   C:\...\enterprise_project\logs\
#
# Como funciona:
#   .parent .parent .parent .parent .parent  =  Sobe 5 pastas de uma vez
#   / "logs"                                 =  Entra na pasta logs
#
# Resultado prático:
#   Quando você usa logger.info() com um arquivo log_file="seu_arquivo.log"
#   O arquivo é criado em: C:\...\enterprise_project\logs\seu_arquivo.log

LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "logs"

def get_logger(name: str, log_file: str = None, level=logging.INFO) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        log_file: Optional filename to save logs
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """

    # "Registrador" (logger) com um nome específico
    # Reutiliza se já existe, cria novo se não existe
    logger = logging.getLogger(name)

    #Se você usar logger.debug("algo") depois disso, essa mensagem não vai aparecer, porque DEBUG é menor que INFO.
    # Ordem de importância (do menor para o maior):
    # DEBUG (detalhe, "eu testei está variável é 42")
    # INFO (informação, "processamento começou")
    #WARNING (aviso, "atenção, algo estranho")
    # ERROR (erro, "algo falhou")
    # CRITICAL (crítico, "aplicação pode quebrar")
    logger.setLevel(level)
    
    # PARTE 1: Configura o "destino" das mensagens (console ou arquivo)
    
    # Verifica se esse logger já tem "destinos" configurados
    # Se já tiver, não faz nada (evita duplicar mensagens)
    # "Se esse logger NÃO tiver nenhum 'destino' (handler) já configurado..."
    if not logger.handlers:
        
        # ========== CONSOLE (Terminal) ==========
        # Cria um "destino" para o console (a tela do terminal)
        console_handler = logging.StreamHandler()
        
        # Define o nível mínimo de mensagens para o console
        console_handler.setLevel(level)
        
        # Define o FORMATO das mensagens que aparecem no console
        # "%(asctime)s"     = Hora e data (ex: 2026-02-26 14:30:45)
        # "%(levelname)s"   = Nível (INFO, ERROR, WARNING, etc)
        # "%(message)s"     = A mensagem em si
        # Resultado: "2026-02-26 14:30:45 | INFO | Iniciando processamento"
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Aplica o formato criado acima no console
        console_handler.setFormatter(formatter)
        
        # Diz ao logger: "Use esse console_handler para mostrar mensagens"
        logger.addHandler(console_handler)
        
        # ========== ARQUIVO (File) ==========
        # Se o usuário especificou um nome de arquivo (log_file)
        if log_file:
            # Cria a pasta "logs" se ela não existir
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Cria um "destino" para um arquivo
            # Exemplo: se log_file="app.log" → cria C:\...\logs\app.log
            file_handler = logging.FileHandler(
                LOG_DIR / log_file,
                encoding="utf-8"  # Suporta acentos e caracteres especiais
            )
            
            # Define o nível mínimo para o arquivo (igual ao console)
            file_handler.setLevel(level)
            
            # Define o FORMATO das mensagens no arquivo
            # Igual ao console, MAS com informação adicional:
            # "%(funcName)s:%(lineno)d" = Nome da função e número da linha
            # Resultado: "2026-02-26 14:30:45 | INFO | processar:42 | Iniciando"
            # Assim você sabe exatamente onde o log foi gerado
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            
            # Aplica o formato criado acima no arquivo
            file_handler.setFormatter(formatter)
            
            # Diz ao logger: "Use esse file_handler para salvar mensagens no arquivo"
            logger.addHandler(file_handler)
    
    # Retorna o logger totalmente configurado e pronto para usar
    return logger
