from src.osap.domain.errors import ResourceUnavailableError
from src.osap.domain.value_objects import DatasetId

def validate_dataset(dataset_id: str) -> dict:
    # Implementar lógica de validación completa aquí
    valid_datasets = ["imslp", "pdmx", "openscore"]
    
    if dataset_id not in valid_datasets:
        raise ResourceUnavailableError(f"Dataset no válido: {dataset_id}")
    
    return {
        "dataset_id": DatasetId(dataset_id),
        "status": "valid",
        "capabilities": {"formats": ["musicxml", "pdf"]}
    }