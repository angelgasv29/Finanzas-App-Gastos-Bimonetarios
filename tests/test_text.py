"""Pruebas de las utilidades de texto."""

from __future__ import annotations

from app.core.text import escape_html


class TestEscapeHtml:
    def test_escapa_los_cinco_caracteres(self) -> None:
        assert escape_html('<b> & "x" </b>') == "&lt;b&gt; &amp; &quot;x&quot; &lt;/b&gt;"

    def test_apostrofe(self) -> None:
        assert escape_html("O'Neill") == "O&#39;Neill"

    def test_null_y_vacio(self) -> None:
        # El operador ?? de la versión de referencia solo sustituye null/undefined.
        assert escape_html(None) == ""
        assert escape_html("") == ""

    def test_cero_se_conserva(self) -> None:
        # Un 0 no es nullish, así que no se sustituye por vacío.
        assert escape_html(0) == "0"

    def test_texto_sin_caracteres_especiales(self) -> None:
        assert escape_html("normal") == "normal"

    def test_cadena_mixta(self) -> None:
        assert escape_html("a & b < c > d \" e ' f") == (
            "a &amp; b &lt; c &gt; d &quot; e &#39; f"
        )
