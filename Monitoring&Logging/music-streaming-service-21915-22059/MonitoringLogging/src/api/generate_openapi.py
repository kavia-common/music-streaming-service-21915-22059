import json
import os

from src.api.main import app

"""
Utility script to regenerate the OpenAPI spec for the Monitoring & Logging container.

Usage:
  python -m src.api.generate_openapi

This will write the OpenAPI document to interfaces/openapi.json at the container root.
"""

# PUBLIC_INTERFACE
def main() -> None:
    """Generate OpenAPI schema from the FastAPI app and write it to interfaces/openapi.json."""
    # Generate schema from the live app
    schema = app.openapi()

    # Ensure interfaces directory exists at container root
    output_dir = os.path.join(os.getcwd(), "interfaces")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "openapi.json")
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI spec written to {output_path}")


if __name__ == "__main__":
    main()
