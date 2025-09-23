from app.core.profiles import ProcessingProfileSettings
from app.parsers.docling import DoclingParserConfig
from app.vector.models import IngestorSettings


class ProfilesService:
    def __init__(self):
        # Minimal in-code catalogue for now; swap to YAML/DB later.
        self._profiles = {
            'default': ProcessingProfileSettings(
                name='default',
                ingestor_config=IngestorSettings(),
                parser_config=DoclingParserConfig(),
            )
        }

    def get(self, name: str = 'default') -> ProcessingProfileSettings:
        return self._profiles.get(name, self._profiles['default'])

    async def get_profiles(self) -> list[ProcessingProfileSettings]:
        return list(self._profiles.values())
