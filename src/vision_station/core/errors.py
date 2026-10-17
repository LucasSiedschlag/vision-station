"""The error-code catalog (architecture §10.3, TD-22, FR-INS-14).

Every ERROR carries one of these codes besides its text. Codes are grouped by cause (E1xx image, E2xx
location, E3xx region or tool, E4xx camera, E5xx system, E6xx machine) so a PLC program or a dashboard
can react by group. A code is never reused or renumbered; its text may be reworded. A new cause gets
the next free number of its group, and the table in architecture §10.3 is updated in the same change.
"""

from dataclasses import dataclass
from enum import IntEnum


class ErrorCode(IntEnum):
    INVALID_IMAGE = 101
    TOO_DARK = 102
    TOO_BRIGHT = 103
    OUT_OF_FOCUS = 104
    COLOR_DRIFT = 105
    NOT_FOUND = 201
    OUT_OF_POSITION = 202
    NOT_FOUND_OR_BLURRED = 203
    LOCATOR_CANNOT_RUN = 204
    REGION_OUTSIDE = 301
    TOOL_CANNOT_RUN = 302
    TOOL_FAILED = 303
    INVALID_SCORE = 304
    CAMERA_LOST = 401
    NO_FRESH_FRAME = 402
    INTERNAL = 501
    NO_JOB = 502
    UNKNOWN_JOB_NUMBER = 503
    VERIFICATION_FAILED = 504
    CHALLENGE = 505
    JOB_SWITCHED = 506
    MACHINE_HEARTBEAT = 601


@dataclass(frozen=True)
class ErrorInfo:
    group: str
    text: str  # pt-BR; the English text comes with the server catalogs (UI-C3, TD-30)
    planned: str = ""  # the refactor or phase that will raise it; empty when the software raises it today


CATALOG: dict[ErrorCode, ErrorInfo] = {
    ErrorCode.INVALID_IMAGE: ErrorInfo("image", "Imagem inválida da câmera"),
    ErrorCode.TOO_DARK: ErrorInfo("image", "Imagem escura demais, verificar a iluminação"),
    ErrorCode.TOO_BRIGHT: ErrorInfo("image", "Imagem clara demais, verificar a iluminação"),
    ErrorCode.OUT_OF_FOCUS: ErrorInfo("image", "Imagem fora de foco, verificar a lente e a câmera"),
    ErrorCode.COLOR_DRIFT: ErrorInfo("image", "Cor de referência fora do limite, verificar iluminação", planned="R5"),
    ErrorCode.NOT_FOUND: ErrorInfo("location", "Objeto não encontrado na posição esperada"),
    ErrorCode.OUT_OF_POSITION: ErrorInfo("location", "Objeto fora da posição ou girado demais", planned="R1"),
    ErrorCode.NOT_FOUND_OR_BLURRED: ErrorInfo("location", "Objeto não encontrado ou imagem fora de foco, verificar a estação e a câmera"),
    ErrorCode.LOCATOR_CANNOT_RUN: ErrorInfo("location", "Localizador não pode rodar"),
    ErrorCode.REGION_OUTSIDE: ErrorInfo("region", "Região fora da imagem"),
    ErrorCode.TOOL_CANNOT_RUN: ErrorInfo("region", "Ferramenta não pode rodar"),
    ErrorCode.TOOL_FAILED: ErrorInfo("region", "Ferramenta falhou"),
    ErrorCode.INVALID_SCORE: ErrorInfo("region", "Ferramenta devolveu pontuação inválida"),
    ErrorCode.CAMERA_LOST: ErrorInfo("camera", "Câmera desconectada durante a inspeção"),
    ErrorCode.NO_FRESH_FRAME: ErrorInfo("camera", "Imagem não recebida da câmera"),
    ErrorCode.INTERNAL: ErrorInfo("system", "Falha interna na inspeção, chamar a manutenção"),
    ErrorCode.NO_JOB: ErrorInfo("system", "Nenhum job ativo e verificado", planned="R3"),
    ErrorCode.UNKNOWN_JOB_NUMBER: ErrorInfo("system", "Número de job desconhecido", planned="R3"),
    ErrorCode.VERIFICATION_FAILED: ErrorInfo("system", "Verificação do job falhou", planned="R3"),
    ErrorCode.CHALLENGE: ErrorInfo("system", "Teste de desafio pendente ou reprovado", planned="R6"),
    ErrorCode.JOB_SWITCHED: ErrorInfo("system", "Troca de job durante a inspeção"),
    ErrorCode.MACHINE_HEARTBEAT: ErrorInfo("machine", "Máquina sem sinal de vida", planned="R3"),
}


# Reason codes of a failing tool, `<tool type>.<criterion>` (FR-INS-14): stable like the error codes, so a
# failure can be counted by cause across jobs. A tool's new criterion adds a code here and in architecture §10.3.
REASON_CODES: dict[str, str] = {
    "code.min_count": "Menos códigos aceitos que o mínimo",
    "code.max_count": "Mais códigos aceitos que o máximo",
    "color.min_fraction": "Fração da região com a cor abaixo do mínimo",
    "color.max_fraction": "Fração da região com a cor acima do máximo",
    "color.min_coverage": "Cobertura ao longo do eixo abaixo do mínimo",
    "color.max_gap": "Maior trecho sem a cor acima do máximo",
    "pattern.min_count": "Menos ocorrências do padrão que o mínimo",
    "pattern.max_count": "Mais ocorrências do padrão que o máximo",
    "pattern.min_coverage": "Cobertura do padrão ao longo do eixo abaixo do mínimo",
    "pattern.max_gap": "Maior trecho sem o padrão acima do máximo",
    "detect.class": "Classe que reprova (ou fora das que aprovam)",
    "detect.min_confidence": "Confiança do modelo abaixo do mínimo",
    "detect.fail_class": "Detecção de uma classe que reprova",
    "detect.require_classes": "Classe obrigatória não detectada",
    "detect.min_count": "Menos detecções da classe contada que o mínimo",
    "detect.max_count": "Mais detecções da classe contada que o máximo",
    "detect.max_score": "Pontuação de anomalia acima do limite",
}
