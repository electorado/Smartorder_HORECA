from pathlib import Path
from typing import List, Dict, Any, Union, Optional

from .extractors import (
    BaseCatalogExtractor,
    detect_supplier_from_pdf,
    GenericExcelExtractor,
    SpatialCardPdfExtractor,
    DialvaPdfExtractor,
    AbordoPdfExtractor,
    TabularPdfExtractor,
    CoordinateTablePdfExtractor,
    VisualFlyerPdfExtractor,
    UniversalPdfExtractor,
    GeminiMultimodalPdfExtractor,
    ExtractorFactory,
)


def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Extrae productos de un fichero Excel."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path)
    return extractor.extract(file_path)


def extract_pdf(
    file_path: Union[str, Path],
    provider_id: Optional[str] = "prov_dialva_04",
    save_output: bool = False
) -> List[Dict[str, Any]]:
    """Extrae productos de un fichero PDF seleccionando la estrategia adecuada."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    if isinstance(extractor, SpatialCardPdfExtractor) and save_output:
        extractor.save_output = True
    return extractor.extract(file_path)


def extract_catalog(
    file_path: Union[str, Path],
    provider_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Detecta el formato de catálogo y extrae los productos."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    return extractor.extract(file_path)


def extract_catalog_with_supplier(
    file_path: Union[str, Path],
    provider_id: Optional[str] = None
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Extrae productos y los datos del proveedor detectado en la cabecera."""
    extractor = ExtractorFactory.get_extractor(file_path=file_path, provider_id=provider_id)
    items = extractor.extract(file_path)
    return items, getattr(extractor, "detected_supplier", None)


def extract_image_list(image_bytes: bytes) -> List[Dict[str, Any]]:
    """Extrae líneas de producto a partir de una foto de libreta o pizarra."""
    from .vision_ai import process_fridge_photo
    return process_fridge_photo(image_bytes)


class CatalogExtractor:
    """Clase helper para agrupar llamadas a los distintos extractores."""

    @staticmethod
    def extract_excel(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        return extract_excel(file_path)

    @staticmethod
    def extract_pdf(
        file_path: Union[str, Path],
        provider_id: Optional[str] = "prov_dialva_04",
        save_output: bool = True
    ) -> List[Dict[str, Any]]:
        return extract_pdf(file_path, provider_id=provider_id, save_output=save_output)

    @staticmethod
    def extract_ocr(image_bytes: bytes) -> List[Dict[str, Any]]:
        return extract_image_list(image_bytes)


__all__ = [
    "BaseCatalogExtractor",
    "detect_supplier_from_pdf",
    "GenericExcelExtractor",
    "SpatialCardPdfExtractor",
    "DialvaPdfExtractor",
    "AbordoPdfExtractor",
    "TabularPdfExtractor",
    "CoordinateTablePdfExtractor",
    "VisualFlyerPdfExtractor",
    "UniversalPdfExtractor",
    "GeminiMultimodalPdfExtractor",
    "ExtractorFactory",
    "extract_excel",
    "extract_pdf",
    "extract_catalog",
    "extract_catalog_with_supplier",
    "extract_image_list",
    "CatalogExtractor",
]
