import base64
from pathlib import Path
import unittest
import os, inspect, io, tempfile
import warnings
import pydocmaker as pyd


class TestDocToPdfTypst(unittest.TestCase):
    """Test cases for compiling documents to PDF using doc.to_pdf(engine='typst').

    Note: Bytes-type attachments (e.g., PNG binary data) are not supported
    by the default typst Rust library which cannot read binary files.
    Tests that use bytes attachments are marked @expectedFailure.
    """

    def test_to_pdf_returns_bytes_by_default(self):
        """Test that to_pdf with engine='typst' returns PDF bytes when path_or_stream is None."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf(engine='typst', verb=0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_pdf_path(self):
        """Test to_pdf with explicit 'pdf' string returns bool (writes to file named 'pdf')."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf('pdf', engine='typst', verb=0)
        # 'pdf' is not '.pdf' or '.zip', so _ret writes to a file named 'pdf' and returns True
        self.assertTrue(result)

    def test_to_pdf_writes_to_pdf_path(self):
        """Test to_pdf writing to a .pdf file path returns True."""
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'output.pdf')
            result = doc.to_pdf(output_path, engine='typst', verb=0)
            self.assertTrue(result)
            saved = Path(output_path).read_bytes()
            self.assertTrue(saved.startswith(b'%PDF'))

    def test_to_pdf_writes_to_io_stream(self):
        """Test to_pdf writing to an in-memory io.BytesIO stream."""
        doc = pyd.Doc.get_example()
        stream = io.BytesIO()
        result = doc.to_pdf(stream, engine='typst', verb=0)
        self.assertTrue(result)
        stream.seek(0)
        data = stream.read()
        self.assertTrue(data.startswith(b'%PDF'))

    def test_to_pdf_with_custom_filename(self):
        """Test to_pdf with a custom docname (filename)."""
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'my_custom_doc.pdf')
            result = doc.to_pdf(output_path, docname='my_custom_doc', engine='typst', verb=0)
            self.assertTrue(result)
            self.assertTrue(Path(output_path).exists())

    def test_to_pdf_with_template_and_params(self):
        """Test to_pdf with template and template_params arguments."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf(
            engine='typst',
            template=None,
            template_params={},
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_template_params_content(self):
        """Test to_pdf with non-trivial template_params."""
        doc = pyd.Doc.get_example()
        tmpl_params = {
            'title': 'Custom Title',
            'author': 'Test Author',
        }
        result = doc.to_pdf(
            engine='typst',
            template_params=tmpl_params,
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_string_attachments(self):
        """Test to_pdf with string-type attachments (inline typst code)."""
        doc = pyd.Doc.get_example()
        attachments = {
            'helper.typ': '# Helper code for testing',
        }
        result = doc.to_pdf(
            engine='typst',
            attachments=attachments,
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))


    def test_to_pdf_with_bytes_attachments(self):
        """Test to_pdf with bytes-type attachments (e.g., image data).

        ExpectedFailure: the typst Rust library cannot read binary files.
        """
        doc = pyd.Doc.get_example()
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        attachments = {
            'logo.png': image_data,
        }
        result = doc.to_pdf(
            engine='typst',
            attachments=attachments,
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_mixed_attachments(self):
        """Test to_pdf with a mix of str and bytes attachments.

        ExpectedFailure: mixed attachments containing bytes fail via the typst Rust library.
        """
        doc = pyd.Doc.get_example()
        attachments = {
            'helper.typ': '# Helper typst code\nlet test() = "hello"',
            'image.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
            'style.typ': '# Style settings\n#set text(size: 10pt)',
        }
        result = doc.to_pdf(
            engine='typst',
            attachments=attachments,
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_additional_files(self):
        """Test to_pdf with additional_files kwarg."""
        doc = pyd.Doc.get_example()
        additional_files = {
            'extra.typ': '# Extra typst content',
        }
        result = doc.to_pdf(
            engine='typst',
            additional_files=additional_files,
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_path_and_string_attachments(self):
        """Test to_pdf writing to a path with string attachments."""
        doc = pyd.Doc.get_example()
        attachments = {
            'extra.typ': '# Extra attachment file',
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'with_attachments.pdf')
            result = doc.to_pdf(
                output_path,
                engine='typst',
                attachments=attachments,
                verb=0,
            )
            self.assertTrue(result)
            saved = Path(output_path).read_bytes()
            self.assertTrue(saved.startswith(b'%PDF'))

    
    def test_to_pdf_with_path_and_bytes_attachments(self):
        """Test to_pdf writing to a path with bytes attachments.

        ExpectedFailure: the typst Rust library cannot read binary files.
        """
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'bytes_attach.pdf')
            image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
            result = doc.to_pdf(
                output_path,
                engine='typst',
                attachments={'logo.png': image_data},
                verb=0,
            )
            self.assertTrue(result)
            saved = Path(output_path).read_bytes()
            self.assertTrue(saved.startswith(b'%PDF'))

    def test_to_pdf_with_on_warning_ignore(self):
        """Test to_pdf with on_warning='ignore'."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf(
            engine='typst',
            on_warning='ignore',
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_on_warning_warn(self):
        """Test to_pdf with on_warning='warn'."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf(
            engine='typst',
            on_warning='warn',
            verb=0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_with_base_dir(self):
        """Test to_pdf with explicit base_dir for temp directory."""
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = doc.to_pdf(
                engine='typst',
                base_dir=tmpdir,
                verb=0,
            )
            self.assertIsNotNone(result)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_base_dir_with_output_path(self):
        """Test to_pdf with base_dir and output file path."""
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'base_dir_out.pdf')
            result = doc.to_pdf(
                output_path,
                engine='typst',
                base_dir=tmpdir,
                verb=0,
            )
            self.assertTrue(result)
            self.assertTrue(Path(output_path).exists())

    def test_to_pdf_full_workflow(self):
        """Test the full workflow: get example doc, dump, convert, compile to PDF."""
        doc = pyd.Doc.get_example()
        result = doc.to_pdf(engine='typst', verb=0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    def test_to_pdf_double_compile(self):
        """Test that compiling the same document twice produces valid results."""
        doc1 = pyd.Doc.get_example()
        result1 = doc1.to_pdf(engine='typst', verb=0)
        doc2 = pyd.Doc.get_example()
        result2 = doc2.to_pdf(engine='typst', verb=0)
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertIsInstance(result1, bytes)
        self.assertIsInstance(result2, bytes)
        self.assertTrue(result1.startswith(b'%PDF'))
        self.assertTrue(result2.startswith(b'%PDF'))

    def test_to_pdf_with_unrecognized_filename(self):
        """Test to_pdf with a filename that doesn't end in .pdf or .zip."""
        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'weirdname')
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                result = doc.to_pdf(output_path, engine='typst', verb=0)
                self.assertTrue(result)
                self.assertTrue(Path(output_path).exists())

    def test_to_pdf_io_stream_with_string_attachments(self):
        """Test to_pdf writing to io.BytesIO with string attachments."""
        doc = pyd.Doc.get_example()
        attachments = {
            'extra.typ': '# inline attachment',
        }
        stream = io.BytesIO()
        result = doc.to_pdf(
            stream,
            engine='typst',
            attachments=attachments,
            verb=0,
        )
        self.assertTrue(result)
        stream.seek(0)
        data = stream.read()
        self.assertTrue(data.startswith(b'%PDF'))

    def test_to_pdf_string_attachment_key_collision(self):
        """Test that multiple attachments with different string keys don't collide."""
        doc = pyd.Doc.get_example()
        attachments1 = {'a.typ': '# set a'}
        result1 = doc.to_pdf(engine='typst', attachments=attachments1, verb=0)
        attachments2 = {'b.typ': '# set b', 'c.typ': '# set c'}
        result2 = doc.to_pdf(engine='typst', attachments=attachments2, verb=0)
        self.assertTrue(result1.startswith(b'%PDF'))
        self.assertTrue(result2.startswith(b'%PDF'))


        
        
    def test_minimal_pdf(self):
        data = pyd.Doc().add('Hello World!').to_pdf(engine='typst', verb=0)
        self.assertTrue(data.startswith(b'%PDF'))

    def test_embed_image(self):
        attachments_bytes = {'mylogo.png': base64.b64decode(pyd.b64_data.logo_b64_pydocmaker)}

        d1 = pyd.Doc().add('Hello World!')
        d2 = pyd.Doc().add('Hello World!\n\n\n#image("mylogo.png", width: 200pt)')
        result = d1.to_pdf(engine='typst', verb=0)
        result_with_img = d2.to_pdf(engine='typst', attachments=attachments_bytes, verb=0)
        self.assertTrue(result.startswith(b'%PDF'))
        self.assertTrue(result_with_img.startswith(b'%PDF'))

        self.assertGreater(len(result_with_img), len(result)*1.1, f'expected a PDF with image to be much bigger than an nearly empty PDF but got: {len(result_with_img)=} vs. {len(result_with_img)=}')

    def test_embed_image_bytes_attachment(self):
        """Test embedding an image using bytes attachment."""
        attachments = {'mylogo.png': base64.b64decode(pyd.b64_data.logo_b64_pydocmaker)}
        doc = pyd.Doc().add('Hello World!\n\n\n#image("mylogo.png", width: 200pt)')
        result = doc.to_pdf(engine='typst', attachments=attachments, verb=0)
        self.assertTrue(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

        r = len(pyd.Doc().add('Hello World!').to_pdf(engine='typst', verb=0))
        self.assertGreater(len(result), r*1.1, f'expected a PDF with image to be much bigger than an nearly empty PDF but got: {len(result)=} vs. {r=}')


    def test_embed_image_path_attachment(self):
        """Test embedding an image using a Path object attachment."""
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            f.write(base64.b64decode(pyd.b64_data.logo_b64_pydocmaker))
            fig_path = Path(f.name)
            
            attachments = {'mylogo.png': fig_path}
            doc = pyd.Doc().add('Hello World!\n\n\n#image("mylogo.png", width: 200pt)')
            result = doc.to_pdf(engine='typst', attachments=attachments, verb=0)
            self.assertTrue(result)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'%PDF'))
            r = len(pyd.Doc().add('Hello World!').to_pdf(engine='typst', verb=0))
            self.assertGreater(len(result), r*1.1, f'expected a PDF with image to be much bigger than an nearly empty PDF but got: {len(result)=} vs. {r=}')



    def test_embed_image_str_path_attachment(self):
        """Test embedding an image using a string path attachment."""
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            f.write(base64.b64decode(pyd.b64_data.logo_b64_pydocmaker))
            fig_path = f.name
        
            attachments = {'mylogo.png': fig_path}
            doc = pyd.Doc().add('Hello World!\n\n\n#image("mylogo.png", width: 200pt)')
            result = doc.to_pdf(engine='typst', attachments=attachments, verb=0)
            self.assertTrue(result)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'%PDF'))

            r = len(pyd.Doc().add('Hello World!').to_pdf(engine='typst', verb=0))
            self.assertGreater(len(result), r*1.1, f'expected a PDF with image to be much bigger than an nearly empty PDF but got: {len(result)=} vs. {r=}')



    def test_error_context(self):
        "test that the context is correctly pared on failed compilation"
        doc = pyd.Doc().add('Hello World!\n\n\n#image("mylogononexisting.png", width: 200pt)')

        with self.assertRaises(Exception) as exc_info:
            doc.to_pdf()
            err = exc_info.value
            self.assertTrue(hasattr(err, 'context'))
            self.assertIsInstance(err.context, dict)
            self.assertTrue(err.context.get('main.typ', None))
            self.assertIsInstance(err.context.get('main.typ', None), (bytes, str))


    def test_error_context2(self):
        "test that the context is correctly pared on failed compilation"
        attachments = {'mylogo.png': base64.b64decode(pyd.b64_data.logo_b64_pydocmaker)}
        doc = pyd.Doc().add('Hello World!\n\n\n#image("mylogononexisting.png", width: 200pt)')
        
        with self.assertRaises(Exception) as exc_info:    
            doc.to_pdf(attachments=attachments)
            err = exc_info.value
            self.assertTrue(hasattr(err, 'context'))
            self.assertIsInstance(err.context, dict)
            self.assertTrue(err.context.get('main.typ', None))
            self.assertIsInstance(err.context.get('main.typ', None), (bytes, str))
            self.assertIsInstance(err.context.get('mylogo.png', None), bytes)



if __name__ == '__main__':
    unittest.main()
