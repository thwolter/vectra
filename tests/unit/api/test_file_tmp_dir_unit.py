import importlib
import io

from starlette.datastructures import Headers, UploadFile


def test_temporary_upload_file_uses_shared_tmp_dir(monkeypatch, tmp_path):
    monkeypatch.setenv('UPLOAD_TMP_DIR', str(tmp_path))
    from api import file as file_module

    importlib.reload(file_module)

    upload = UploadFile(
        filename='sample.pdf',
        file=io.BytesIO(b'content'),
        headers=Headers({'content-type': 'application/pdf'}),
    )

    temp_file = file_module.TemporaryUploadFile.from_upload(upload)

    assert temp_file.path.exists()
    assert temp_file.path.parent == tmp_path

    temp_file.close()
