"""Pruebas de la capa de datos (``app/data``).

Verifican que el repositorio replica la API del objeto ``DB`` de la versión de referencia
exactamente donde importa: claves, orden de resultados, semántica de índices y
tratamiento de valores especiales.
"""

from __future__ import annotations

import itertools
import tempfile
from pathlib import Path

import pytest

from app.core.constants import CAT_COLORS
from app.data.db import Database
from app.data.repo import Repository
from app.data.seed import seed_categories_if_empty


@pytest.fixture()
def db_path() -> Path:
    return Path(tempfile.mkdtemp()) / "prueba.sqlite3"


@pytest.fixture()
def db(db_path: Path) -> Database:
    database = Database(db_path).initialize()
    yield database
    database.close()


@pytest.fixture()
def repo(db: Database) -> Repository:
    return Repository(db)


def make_category(cat_id: str = "cat_1", workspace: str = "personal") -> dict:
    return {
        "id": cat_id,
        "workspace": workspace,
        "name": "Alimentación",
        "color": "#2563EB",
        "enabledFields": {"quantity": True, "unit": True},
        "customFields": [{"id": "cf_1", "label": "Empaque", "type": "text", "required": False}],
        "createdAt": 1700000000000,
        "updatedAt": 1700000000000,
    }


def make_transaction(**overrides: object) -> dict:
    record = {
        "workspace": "personal",
        "year": 2026,
        "date": "2026-03-15",
        "productName": "Harina PAN",
        "categoryId": "cat_1",
        "quantity": 2.0,
        "unit": "kg",
        "brand": "PAN",
        "baseImponible": 100.0,
        "ivaMonto": 16.0,
        "amountBs": 116.0,
        "amountUsd": 3.1657,
        "rate": 36.64,
        "rateDate": "2026-03-15",
        "rateSource": "manual",
        "customValues": {},
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------


def test_esquema_crea_los_cinco_almacenes_mas_config(db: Database) -> None:
    assert db.table_names() == [
        "categories",
        "closures",
        "config",
        "products",
        "rates",
        "transactions",
    ]


def test_indices_equivalentes_a_los_de_indexeddb(db: Database) -> None:
    assert db.index_names("categories") == ["idx_categories_workspace"]
    assert set(db.index_names("transactions")) == {
        "idx_tx_workspace",
        "idx_tx_date",
        "idx_tx_workspace_date",
        "idx_tx_product",
        "idx_tx_year",
        "idx_tx_workspace_year",
    }
    assert set(db.index_names("products")) == {
        "idx_products_workspace",
        "idx_products_name_lower",
        "idx_products_category",
    }
    assert db.index_names("rates") == ["idx_rates_date"]
    assert db.index_names("closures") == ["idx_closures_workspace_year"]


def test_inicializar_dos_veces_es_idempotente(db: Database) -> None:
    db.initialize()  # no debe lanzar
    assert db.table_names() == [
        "categories",
        "closures",
        "config",
        "products",
        "rates",
        "transactions",
    ]


def test_la_base_de_datos_persiste_al_reabrir(db_path: Path) -> None:
    first = Database(db_path).initialize()
    Repository(first).put("categories", make_category())
    first.close()

    second = Database(db_path).initialize()
    try:
        assert Repository(second).get("categories", "cat_1")["name"] == "Alimentación"
    finally:
        second.close()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_put_y_get_de_categoria(repo: Repository) -> None:
    repo.put("categories", make_category())
    loaded = repo.get("categories", "cat_1")
    assert loaded is not None
    assert loaded["name"] == "Alimentación"
    assert loaded["enabledFields"] == {"quantity": True, "unit": True}
    assert loaded["customFields"][0]["label"] == "Empaque"


def test_put_actualiza_si_la_clave_existe(repo: Repository) -> None:
    repo.put("categories", make_category())
    repo.put("categories", {**make_category(), "name": "Comida"})
    assert repo.count("categories") == 1
    assert repo.get("categories", "cat_1")["name"] == "Comida"


def test_put_reemplaza_el_registro_entero_como_indexeddb(repo: Repository) -> None:
    # IndexedDB.put sustituye el registro completo: una propiedad ausente vuelve
    # a su valor por defecto, no se conserva. La versión de referencia nunca guarda registros
    # parciales, así que esta implementación tampoco debe poder hacerlo por descuido.
    repo.put("categories", make_category())
    repo.put("categories", {"id": "cat_1", "workspace": "personal", "name": "Otra"})
    loaded = repo.get("categories", "cat_1")
    assert loaded["name"] == "Otra"
    assert loaded["color"] == "#2563EB"  # valor por defecto, no el anterior
    assert loaded["enabledFields"] == {}
    assert loaded["customFields"] == []


def test_get_inexistente_devuelve_none(repo: Repository) -> None:
    assert repo.get("categories", "no-existe") is None


def test_delete_y_clear(repo: Repository) -> None:
    repo.put("categories", make_category("cat_1"))
    repo.put("categories", make_category("cat_2"))
    repo.delete("categories", "cat_1")
    assert repo.count("categories") == 1
    repo.clear("categories")
    assert repo.count("categories") == 0


def test_clear_all_vacia_los_cinco_almacenes(repo: Repository) -> None:
    repo.put("categories", make_category())
    repo.put("products", {"id": "PROD-P-1", "workspace": "personal", "name": "A", "name_lower": "a"})
    repo.add("transactions", make_transaction())
    repo.put("rates", {"date": "2026-03-15", "value": 36.64, "source": "manual"})
    repo.put("closures", {"id": "clo_1", "workspace": "personal", "year": 2026})

    repo.clear_all()

    assert repo.storage_stats()["categories"] == 0
    assert repo.storage_stats()["transactions"] == 0


def test_add_de_transaccion_asigna_ids_enteros_crecientes(repo: Repository) -> None:
    first = repo.add("transactions", make_transaction())
    second = repo.add("transactions", make_transaction(date="2026-03-16"))
    assert (first, second) == (1, 2)
    assert isinstance(repo.get("transactions", first)["id"], int)


def test_add_con_createdat_explicito_no_lo_pisa(repo: Repository) -> None:
    tx_id = repo.add("transactions", make_transaction(createdAt=1234, updatedAt=5678))
    loaded = repo.get("transactions", tx_id)
    assert (loaded["createdAt"], loaded["updatedAt"]) == (1234, 5678)


def test_add_rellena_las_marcas_de_tiempo_si_faltan(repo: Repository) -> None:
    tx_id = repo.add("transactions", make_transaction())
    loaded = repo.get("transactions", tx_id)
    assert loaded["createdAt"] > 0
    assert loaded["createdAt"] == loaded["updatedAt"]


def test_put_de_transaccion_con_id_actualiza_en_su_sitio(repo: Repository) -> None:
    tx_id = repo.add("transactions", make_transaction())
    repo.put("transactions", {**make_transaction(), "id": tx_id, "amountBs": 999.0})
    assert repo.count("transactions") == 1
    assert repo.get("transactions", tx_id)["amountBs"] == 999.0


def test_put_de_transaccion_sin_id_inserta(repo: Repository) -> None:
    # Equivale a DB.put con una transacción nueva.
    key = repo.put("transactions", make_transaction())
    assert repo.count("transactions") == 1
    assert key == 1


def test_add_many_inserta_en_bloque(repo: Repository) -> None:
    total = repo.add_many(
        "transactions",
        [make_transaction(date=f"2026-03-{day:02d}") for day in range(1, 6)],
    )
    assert total == 5
    assert repo.count("transactions") == 5


def test_add_many_es_atomico(db: Database, repo: Repository) -> None:
    class Roto(Exception):
        pass

    records = [make_transaction(), make_transaction()]
    records[1]["customValues"] = Roto()  # no es serializable en JSON

    with pytest.raises(TypeError):
        repo.add_many("transactions", records)

    # La transacción implícita de add_many deja el almacén intacto.
    assert repo.count("transactions") == 0


# ---------------------------------------------------------------------------
# JSON y valores especiales
# ---------------------------------------------------------------------------


def test_los_campos_json_sobreviven_el_viaje_de_ida_y_vuelta(repo: Repository) -> None:
    repo.add(
        "transactions",
        make_transaction(customValues={"presentacion": "1kg", "n": 3, "ok": True}),
    )
    loaded = repo.all("transactions")[0]
    assert loaded["customValues"] == {"presentacion": "1kg", "n": 3, "ok": True}


def test_las_listas_de_cierre_sobreviven_el_viaje(repo: Repository) -> None:
    top_categories = [{"name": "Salud", "color": "#10B981", "total": 12.5, "count": 2}]
    top_expenses = [{"name": "Paracetamol", "totalBs": 100.0, "totalUsd": 2.7}]
    repo.put(
        "closures",
        {
            "id": "clo_1",
            "workspace": "personal",
            "year": 2026,
            "topCategories": top_categories,
            "topExpenses": top_expenses,
        },
    )
    loaded = repo.get("closures", "clo_1")
    assert loaded["topCategories"] == top_categories
    assert loaded["topExpenses"] == top_expenses


def test_los_campos_json_ausentes_toman_el_valor_por_defecto(repo: Repository) -> None:
    repo.put("categories", {"id": "cat_x", "workspace": "personal", "name": "Suelta"})
    loaded = repo.get("categories", "cat_x")
    assert loaded["enabledFields"] == {}
    assert loaded["customFields"] == []

    tx_id = repo.add("transactions", {"workspace": "personal", "year": 2026, "date": "2026-01-01"})
    assert repo.get("transactions", tx_id)["customValues"] == {}


def test_las_columnas_ausentes_usan_los_default_del_esquema(repo: Repository) -> None:
    tx_id = repo.add("transactions", {"workspace": "personal", "year": 2026, "date": "2026-01-01"})
    loaded = repo.get("transactions", tx_id)
    assert loaded["amountBs"] == 0.0
    assert loaded["amountUsd"] == 0.0
    assert loaded["notes"] == ""
    assert loaded["quantity"] is None
    assert loaded["rate"] is None


def test_nan_se_guarda_como_null(repo: Repository) -> None:
    # IndexedDB conserva NaN; SQLite lo almacena como NULL. Se hace explícito.
    tx_id = repo.add("transactions", make_transaction(quantity=float("nan")))
    assert repo.get("transactions", tx_id)["quantity"] is None


def test_la_cantidad_no_numerica_queda_en_null(repo: Repository) -> None:
    # La versión de referencia hace parseFloat(...) y guarda undefined/null si no hay número.
    tx_id = repo.add("transactions", make_transaction(quantity=None))
    assert repo.get("transactions", tx_id)["quantity"] is None


# ---------------------------------------------------------------------------
# Consultas por índice
# ---------------------------------------------------------------------------


def test_query_por_workspace(repo: Repository) -> None:
    repo.put("categories", make_category("cat_1", "personal"))
    repo.put("categories", make_category("cat_2", "profesional"))
    personal = repo.query_by_index("categories", "workspace", "personal")
    assert [c["id"] for c in personal] == ["cat_1"]


def test_query_workspace_year_no_mezcla_entornos_ni_anos(repo: Repository) -> None:
    repo.add("transactions", make_transaction(workspace="personal", year=2026))
    repo.add("transactions", make_transaction(workspace="profesional", year=2026))
    repo.add("transactions", make_transaction(workspace="personal", year=2025))

    assert len(repo.query_by_index("transactions", "workspace_year", ("personal", 2026))) == 1
    assert len(repo.query_by_index("transactions", "workspace_year", ("profesional", 2026))) == 1
    assert len(repo.query_by_index("transactions", "workspace_year", ("personal", 2025))) == 1
    assert len(repo.transactions_for_year("personal", 2024)) == 0


def test_query_workspace_date(repo: Repository) -> None:
    repo.add("transactions", make_transaction(date="2026-03-15"))
    repo.add("transactions", make_transaction(date="2026-03-16"))
    found = repo.query_by_index("transactions", "workspace_date", ("personal", "2026-03-15"))
    assert [t["date"] for t in found] == ["2026-03-15"]


def test_query_por_producto(repo: Repository) -> None:
    repo.add("transactions", make_transaction(productId="PROD-P-AAAA1111"))
    repo.add("transactions", make_transaction(productId="PROD-P-BBBB2222"))
    found = repo.query_by_index("transactions", "productId", "PROD-P-AAAA1111")
    assert len(found) == 1


def test_indice_desconocido_lanza_error_claro(repo: Repository) -> None:
    with pytest.raises(ValueError, match="No existe el indice 'inventado' en 'rates'"):
        repo.query_by_index("rates", "inventado", "2026-01-01")


def test_el_orden_de_all_sigue_las_claves_como_indexeddb(repo: Repository) -> None:
    # rates tiene keyPath 'date': getAll devuelve orden ascendente por fecha.
    for date in ("2026-03-15", "2026-01-10", "2026-02-20"):
        repo.put("rates", {"date": date, "value": 36.0, "source": "manual"})
    assert [r["date"] for r in repo.all("rates")] == [
        "2026-01-10",
        "2026-02-20",
        "2026-03-15",
    ]


def test_las_transacciones_de_all_conservan_el_orden_de_insercion(repo: Repository) -> None:
    for date in ("2026-03-15", "2026-01-10", "2026-02-20"):
        repo.add("transactions", make_transaction(date=date))
    assert [t["date"] for t in repo.all("transactions")] == [
        "2026-03-15",
        "2026-01-10",
        "2026-02-20",
    ]


# ---------------------------------------------------------------------------
# Consultas de conveniencia
# ---------------------------------------------------------------------------


def test_rates_desc_y_asc(repo: Repository) -> None:
    for date in ("2026-01-10", "2026-03-15", "2026-02-20"):
        repo.put("rates", {"date": date, "value": 36.0, "source": "manual"})
    assert [r["date"] for r in repo.rates_desc()] == [
        "2026-03-15",
        "2026-02-20",
        "2026-01-10",
    ]
    assert [r["date"] for r in repo.rates_asc()][0] == "2026-01-10"


def test_rates_for_year(repo: Repository) -> None:
    repo.put("rates", {"date": "2025-12-31", "value": 35.0})
    repo.put("rates", {"date": "2026-01-10", "value": 36.0})
    repo.put("rates", {"date": "2026-03-15", "value": 37.0})
    found = repo.rates_for_year(2026)
    assert [r["date"] for r in found] == ["2026-01-10", "2026-03-15"]


def test_find_product_by_name_ignora_mayusculas_y_entorno(repo: Repository) -> None:
    repo.put(
        "products",
        {"id": "PROD-P-1", "workspace": "personal", "name": "Harina PAN", "name_lower": "harina pan"},
    )
    repo.put(
        "products",
        {"id": "PROD-W-1", "workspace": "profesional", "name": "Harina PAN", "name_lower": "harina pan"},
    )
    found = repo.find_product_by_name("personal", "HARINA pan")
    assert found is not None
    assert found["id"] == "PROD-P-1"
    assert repo.find_product_by_name("personal", "no existe") is None


def test_closures_for_ordena_por_ano_descendente(repo: Repository) -> None:
    for year in (2024, 2026, 2025):
        repo.put("closures", {"id": f"clo_{year}", "workspace": "personal", "year": year})
    assert [c["year"] for c in repo.closures_for("personal")] == [2026, 2025, 2024]


def test_storage_stats_cuenta_por_almacen_y_config(repo: Repository) -> None:
    repo.put("categories", make_category())
    repo.add("transactions", make_transaction())
    repo.set_config("gb_theme", "dark")

    stats = repo.storage_stats()
    assert stats["categories"] == 1
    assert stats["transactions"] == 1
    assert stats["products"] == 0
    assert stats["configKeys"] == 1


# ---------------------------------------------------------------------------
# Configuración (reemplazo de localStorage)
# ---------------------------------------------------------------------------


def test_config_guardar_leer_y_borrar(repo: Repository) -> None:
    assert repo.get_config("gb_theme") is None
    assert repo.get_config("gb_theme", "light") == "light"

    repo.set_config("gb_theme", "dark")
    assert repo.get_config("gb_theme") == "dark"

    repo.set_config("gb_theme", "light")
    assert repo.get_config("gb_theme") == "light"

    repo.remove_config("gb_theme")
    assert repo.get_config("gb_theme") is None


def test_config_guarda_todo_como_texto_igual_que_lsSet(repo: Repository) -> None:
    # La versión de referencia hace localStorage.setItem(k, String(v)).
    repo.set_config("gb_fiscal_year", 2026)
    assert repo.get_config("gb_fiscal_year") == "2026"

    repo.set_config("gb_session_rate", None)
    assert repo.get_config("gb_session_rate") == "null"

    repo.set_config("gb_default_workspace", "personal")
    assert repo.get_config("gb_default_workspace") == "personal"


def test_config_keys_y_clear(repo: Repository) -> None:
    repo.set_config("gb_b", "2")
    repo.set_config("gb_a", "1")
    assert repo.config_keys() == ["gb_a", "gb_b"]
    repo.clear_config()
    assert repo.config_keys() == []


# ---------------------------------------------------------------------------
# Transacciones de SQLite
# ---------------------------------------------------------------------------


def test_tx_se_revierte_entera_si_falla(db: Database, repo: Repository) -> None:
    class Fallo(Exception):
        pass

    with pytest.raises(Fallo):
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO categories (id, workspace, name) VALUES ('cat_1','personal','A')"
            )
            conn.execute(
                "INSERT INTO categories (id, workspace, name) VALUES ('cat_2','personal','B')"
            )
            raise Fallo()

    assert repo.count("categories") == 0


def test_tx_aplica_todo_si_no_hay_error(db: Database, repo: Repository) -> None:
    with db.tx() as conn:
        for index in range(3):
            conn.execute(
                "INSERT INTO categories (id, workspace, name) VALUES (?,?,?)",
                (f"cat_{index}", "personal", f"C{index}"),
            )
    assert repo.count("categories") == 3


# ---------------------------------------------------------------------------
# Semilla de categorías
# ---------------------------------------------------------------------------


def test_semilla_crea_cuatro_personales_y_tres_profesionales(repo: Repository) -> None:
    assert seed_categories_if_empty(repo) == 7
    # El orden de lectura es el de IndexedDB (por clave primaria), y los id son
    # aleatorios: se compara como conjunto.
    assert sorted(c["name"] for c in repo.categories_for("personal")) == sorted(
        [
            "Alimentación y Abastecimiento",
            "Salud y Farmacia",
            "Servicios y Conectividad",
            "Transporte y Movilidad",
        ]
    )
    assert sorted(c["name"] for c in repo.categories_for("profesional")) == sorted(
        ["Insumos e Inventario", "Operaciones y SaaS", "Honorarios y Logística"]
    )


def test_semilla_usa_los_colores_por_defecto(repo: Repository) -> None:
    seed_categories_if_empty(repo)
    personal = {c["name"]: c["color"] for c in repo.categories_for("personal")}
    assert personal == {
        "Alimentación y Abastecimiento": CAT_COLORS["alimentacion"],
        "Salud y Farmacia": CAT_COLORS["salud"],
        "Servicios y Conectividad": CAT_COLORS["servicios"],
        "Transporte y Movilidad": CAT_COLORS["transporte"],
    }
    profesional = {c["name"]: c["color"] for c in repo.categories_for("profesional")}
    assert profesional == {
        "Insumos e Inventario": CAT_COLORS["insumos"],
        "Operaciones y SaaS": CAT_COLORS["operaciones"],
        "Honorarios y Logística": CAT_COLORS["honorarios"],
    }


def test_semilla_es_idempotente(repo: Repository) -> None:
    seed_categories_if_empty(repo)
    assert seed_categories_if_empty(repo) == 0
    assert repo.count("categories") == 7


def test_semilla_no_toca_un_entorno_que_ya_tiene_categorias(repo: Repository) -> None:
    repo.put("categories", make_category("cat_propia", "personal"))
    assert seed_categories_if_empty(repo) == 3  # solo siembra profesional
    assert repo.count("categories") == 4


def test_semilla_habilita_platforma_origen_siempre(repo: Repository) -> None:
    # Línea 3074: si el campo no está declarado en la semilla, se habilita.
    seed_categories_if_empty(repo)
    for category in repo.all("categories"):
        assert category["enabledFields"]["originPlatform"] is True


def test_semilla_campos_habilitados_por_tipo(repo: Repository) -> None:
    seed_categories_if_empty(repo)
    personal = {c["name"]: c for c in repo.categories_for("personal")}

    alimentacion = personal["Alimentación y Abastecimiento"]["enabledFields"]
    assert alimentacion["quantity"] is True
    assert alimentacion["unit"] is True
    assert alimentacion["brand"] is True

    servicios = personal["Servicios y Conectividad"]["enabledFields"]
    assert servicios["quantity"] is False
    assert servicios["unit"] is False
    assert servicios["subcategory"] is True


def test_semilla_genera_identificadores_distintos_con_su_prefijo(repo: Repository) -> None:
    counter = itertools.count()
    seed_categories_if_empty(repo, id_factory=lambda prefix: f"{prefix}_{next(counter)}")

    categories = repo.all("categories")
    assert len({c["id"] for c in categories}) == 7  # no se pisan entre sí
    for category in categories:
        assert category["id"].startswith("cat_")
        for field in category["customFields"]:
            assert field["id"].startswith("cf_")


def test_semilla_campos_personalizados_de_cada_categoria(repo: Repository) -> None:
    seed_categories_if_empty(repo)
    by_name = {c["name"]: c for c in repo.all("categories")}
    assert [f["label"] for f in by_name["Alimentación y Abastecimiento"]["customFields"]] == [
        "Presentación / Empaque"
    ]
    assert [f["label"] for f in by_name["Transporte y Movilidad"]["customFields"]] == [
        "Kilometraje"
    ]
    assert by_name["Transporte y Movilidad"]["customFields"][0]["type"] == "number"
    assert [f["label"] for f in by_name["Insumos e Inventario"]["customFields"]] == [
        "RIF Proveedor",
        "Nro. Control Fiscal",
    ]


def test_semilla_acepta_una_lista_de_entornos(repo: Repository) -> None:
    assert seed_categories_if_empty(repo, workspaces=("personal",)) == 4
    assert repo.count("categories") == 4
