from pathlib import Path
from typing import Optional, Union, Dict, Any, List

from .base import BaseCatalogExtractor
from .excel import GenericExcelExtractor
from .pdf_spatial import SpatialCardPdfExtractor, DialvaPdfExtractor, AbordoPdfExtractor
from .pdf_tabular import TabularPdfExtractor, CoordinateTablePdfExtractor
from .pdf_universal import VisualFlyerPdfExtractor, UniversalPdfExtractor, GeminiMultimodalPdfExtractor


class ExtractorFactory:
    """Factoría responsable de instanciar y devolver la estrategia de extracción adecuada.
    
    Satisface el principio Open/Closed: para agregar soporte a nuevos formatos o
    proveedores, basta con registrar una nueva clase en el catálogo sin modificar
    el cliente ni el pipeline ETL.
    """

    _REGISTRY: Dict[tuple, Any] = {
        ("excel", None): GenericExcelExtractor,
        ("excel", "prov_paco_01"): GenericExcelExtractor,
        ("pdf", "prov_dialva_04"): DialvaPdfExtractor,
        ("pdf", "dialva"): DialvaPdfExtractor,
        ("pdf", "prov_abordo_02"): AbordoPdfExtractor,
        ("pdf", "abordo"): AbordoPdfExtractor,
        ("pdf", "gemini"): GeminiMultimodalPdfExtractor,
        ("pdf", "auto"): UniversalPdfExtractor,
        ("pdf", "nuevo"): UniversalPdfExtractor,
        ("pdf", None): UniversalPdfExtractor,  # Por defecto extractor universal adaptativo
    }

    @classmethod
    def register(cls, file_type: str, provider_id: Optional[str], extractor_class: type):
        """Permite registrar dinámicamente nuevas estrategias en tiempo de ejecución."""
        cls._REGISTRY[(file_type.lower(), provider_id)] = extractor_class

    @classmethod
    def get_extractor(
        cls,
        file_path: Union[str, Path],
        provider_id: Optional[str] = None
    ) -> BaseCatalogExtractor:
        """Determina y crea la instancia del extractor adecuado según extensión y proveedor."""
        path = Path(file_path)
        ext = path.suffix.lower().strip('.')

        file_type = "excel" if ext in ["xlsx", "xls"] else "pdf" if ext == "pdf" else ext

        # 1. Búsqueda por par exacto (tipo, proveedor)
        if provider_id and (file_type, provider_id.lower()) in cls._REGISTRY:
            return cls._REGISTRY[(file_type, provider_id.lower())]()

        # 2. Si el proveedor contiene 'dialva' o el archivo es el catálogo de Dialva
        if "dialva" in path.stem.lower() or (provider_id and "dialva" in provider_id.lower()):
            return DialvaPdfExtractor()

        # 2.1. Si el proveedor contiene 'abordo' o 'servifrio' o el archivo es de Abordo
        if any(k in path.stem.lower() for k in ["abordo", "servifrio", "servifrío"]) or (
            provider_id and any(k in provider_id.lower() for k in ["abordo", "servifrio", "servifrío"])
        ):
            return AbordoPdfExtractor()

        # 3. Fallback genérico por tipo de archivo
        if (file_type, None) in cls._REGISTRY:
            return cls._REGISTRY[(file_type, None)]()

        raise ValueError(f"No hay una estrategia de extracción registrada para tipo='{file_type}', proveedor='{provider_id}'")


# --- Funciones de extracción y compatibilidad ---

