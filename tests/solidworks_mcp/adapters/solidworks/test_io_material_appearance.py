"""Coverage tests for the material/appearance/interference capabilities added
to :class:`SolidWorksIOMixin`, plus the helpers they depend on.

This branch added ``check_interference``, ``set_material``, ``set_appearance``
and ``get_material_properties`` to ``adapters/solidworks/io.py``. They were
verified against real SolidWorks but had little to no unit coverage. Every
guard clause (no active model, wrong document type, empty material name,
out-of-range colour channels) and every read-back-mismatch failure path
exercised here is reachable with a fake in-process COM model - no COM
connection required - so each test asserts on the actual returned payload or
error message, not merely that a call completed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus
from solidworks_mcp.adapters.solidworks import io as _io_module
from solidworks_mcp.adapters.solidworks.io import (
    SolidWorksIOMixin,
    _bounding_box_tuple,
    _byref_bstr,
    _byref_int,
    _doc_type,
    _read_material_name,
    _variant_doubles,
)


class _IOHarness(SolidWorksIOMixin):
    """Minimal stand-in for ``PyWin32Adapter`` exercising only the IO mixin."""

    def __init__(self, current_model: object | None = None, swApp: object | None = None) -> None:
        self.currentModel = current_model
        self.swApp = swApp
        self._active_doc_path = None

    def _attempt(self, callback, default=None):
        try:
            return callback()
        except Exception:
            return default

    def _get_attr_or_call(self, obj, attr_name):
        attr = getattr(obj, attr_name, None)
        return attr() if callable(attr) else attr

    def _handle_com_operation(self, _name, callback, *args, **kwargs):
        try:
            return AdapterResult(
                status=AdapterResultStatus.SUCCESS, data=callback(*args, **kwargs)
            )
        except Exception as exc:
            return AdapterResult(status=AdapterResultStatus.ERROR, error=str(exc))

    def is_connected(self):
        return True


# --------------------------------------------------------------------------
# check_interference
# --------------------------------------------------------------------------


class TestCheckInterference:
    @pytest.mark.asyncio
    async def test_requires_active_model(self) -> None:
        adapter = _IOHarness(current_model=None)
        result = await adapter.check_interference()
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active model"

    @pytest.mark.asyncio
    async def test_requires_assembly_document(self) -> None:
        model = SimpleNamespace(GetType=lambda: 1)
        adapter = _IOHarness(current_model=model)
        result = await adapter.check_interference()
        assert result.status == AdapterResultStatus.ERROR
        assert "requires an assembly document" in result.error
        assert "expected 2" in result.error

    @pytest.mark.asyncio
    async def test_reports_zero_interferences_honestly(self) -> None:
        model = SimpleNamespace(GetType=lambda: 2, ToolsCheckInterference2=lambda *a: 0)
        adapter = _IOHarness(current_model=model)
        result = await adapter.check_interference()
        assert result.is_success
        assert result.data["interference_found"] is False
        assert result.data["interference_count"] == 0
        assert result.data["interferences"] == []
        assert result.data["coincident_treated_as_interference"] is False

    @pytest.mark.asyncio
    async def test_reports_bare_count_without_component_list(self) -> None:
        model = SimpleNamespace(GetType=lambda: 2, ToolsCheckInterference2=lambda *a: 3)
        adapter = _IOHarness(current_model=model)
        result = await adapter.check_interference()
        assert result.is_success
        assert result.data["interference_count"] == 3
        assert result.data["interference_found"] is True
        assert result.data["interferences"] == []

    @pytest.mark.asyncio
    async def test_reports_component_pairs_using_name2(self) -> None:
        comp_a = SimpleNamespace(Name2="PartA-1")
        comp_b = SimpleNamespace(Name2="PartB-1")
        model = SimpleNamespace(
            GetType=lambda: 2,
            ToolsCheckInterference2=lambda *a: (2, [comp_a, comp_b]),
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.check_interference({"coincident": True})
        assert result.is_success
        assert result.data["interference_count"] == 2
        assert result.data["interferences"] == [
            {"component_1": "PartA-1", "component_2": "PartB-1"}
        ]
        assert result.data["coincident_treated_as_interference"] is True

    @pytest.mark.asyncio
    async def test_falls_back_to_select_by_id_string_when_name2_missing(self) -> None:
        comp_a = SimpleNamespace(GetSelectByIDString=lambda: "Comp1@Assem")
        comp_b = SimpleNamespace()  # neither Name2 nor GetSelectByIDString
        model = SimpleNamespace(
            GetType=lambda: 2,
            ToolsCheckInterference2=lambda *a: (2, [comp_a, comp_b]),
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.check_interference()
        assert result.data["interferences"] == [
            {"component_1": "Comp1@Assem", "component_2": "<unnamed>"}
        ]


# --------------------------------------------------------------------------
# set_material
# --------------------------------------------------------------------------


def _material_model(get_material_name, *, doc_type: int = 1):
    calls: dict[str, object] = {}

    def _set_material_property_name2(config_name, database, name):
        calls["config_name"] = config_name
        calls["database"] = database
        calls["name"] = name
        return None

    model = SimpleNamespace(
        GetType=lambda: doc_type,
        GetActiveConfiguration=lambda: SimpleNamespace(Name="Default"),
        SetMaterialPropertyName2=_set_material_property_name2,
        ForceRebuild3=lambda *_a: True,
        GetMaterialPropertyName2=get_material_name,
    )
    return model, calls


class TestSetMaterial:
    @pytest.mark.asyncio
    async def test_requires_active_model(self) -> None:
        adapter = _IOHarness(current_model=None)
        result = await adapter.set_material("6061 Alloy")
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active model"

    @pytest.mark.asyncio
    async def test_rejects_blank_name(self) -> None:
        model, _ = _material_model(lambda *a: "x")
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_material("   ")
        assert result.status == AdapterResultStatus.ERROR
        assert "requires a material name" in result.error

    @pytest.mark.asyncio
    async def test_requires_part_document(self) -> None:
        model, _ = _material_model(lambda *a: "x", doc_type=2)
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_material("6061 Alloy")
        assert result.status == AdapterResultStatus.ERROR
        assert "requires a part document" in result.error
        assert "expected 1" in result.error

    @pytest.mark.asyncio
    async def test_success_reads_back_the_applied_material(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = "solidworks materials.sldmat"
            return "6061 Alloy"

        model, calls = _material_model(get_material_name)
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_material("6061 alloy", database="C:/mats.sldmat")

        assert result.is_success
        assert result.data["name"] == "6061 Alloy"
        assert result.data["database"] == "solidworks materials.sldmat"
        assert result.data["configuration"] == "Default"
        # Confirms the resolved (explicit) database, not a default lookup.
        assert calls["database"] == "C:/mats.sldmat"
        assert calls["name"] == "6061 alloy"

    @pytest.mark.asyncio
    async def test_raises_when_readback_does_not_match_requested_name(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = ""
            return "Plain Carbon Steel"

        model, _ = _material_model(get_material_name)
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_material("6061 Alloy", database="C:/mats.sldmat")

        assert result.status == AdapterResultStatus.ERROR
        assert "Material did not take" in result.error
        assert "6061 Alloy" in result.error
        assert "Plain Carbon Steel" in result.error

    @pytest.mark.asyncio
    async def test_falls_back_to_default_database_when_none_given(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = ""
            return "6061 Alloy"

        model, calls = _material_model(get_material_name)
        # No swApp configured -> _default_material_database() short-circuits to "".
        adapter = _IOHarness(current_model=model, swApp=None)
        result = await adapter.set_material("6061 Alloy")

        assert result.is_success
        assert calls["database"] == ""
        assert result.data["database"] == ""


class TestDefaultMaterialDatabase:
    def test_returns_empty_when_swapp_is_none(self) -> None:
        adapter = _IOHarness(current_model=None, swApp=None)
        assert adapter._default_material_database() == ""

    def test_returns_empty_when_executable_path_unreadable(self) -> None:
        app = SimpleNamespace(GetExecutablePath=lambda: None)
        adapter = _IOHarness(swApp=app)
        assert adapter._default_material_database() == ""

    def test_finds_english_candidate_under_lang_root(self, tmp_path) -> None:
        sld_dir = tmp_path / "lang" / "english" / "sldmaterials"
        sld_dir.mkdir(parents=True)
        target = sld_dir / "solidworks materials.sldmat"
        target.write_text("placeholder")

        app = SimpleNamespace(GetExecutablePath=lambda: str(tmp_path / "sldworks.exe"))
        adapter = _IOHarness(swApp=app)

        assert adapter._default_material_database() == str(target)

    def test_walks_lang_root_for_other_locale_directories(self, tmp_path) -> None:
        # "english" is absent, so the hardcoded candidates both miss and the
        # function must fall back to walking every entry under lang/.
        sld_dir = tmp_path / "lang" / "chinese" / "sldmaterials"
        sld_dir.mkdir(parents=True)
        target = sld_dir / "solidworks materials.sldmat"
        target.write_text("placeholder")

        app = SimpleNamespace(GetExecutablePath=lambda: str(tmp_path / "sldworks.exe"))
        adapter = _IOHarness(swApp=app)

        assert adapter._default_material_database() == str(target)

    def test_returns_empty_when_nothing_matches_anywhere(self, tmp_path) -> None:
        (tmp_path / "lang" / "japanese").mkdir(parents=True)
        app = SimpleNamespace(GetExecutablePath=lambda: str(tmp_path / "sldworks.exe"))
        adapter = _IOHarness(swApp=app)

        assert adapter._default_material_database() == ""


# --------------------------------------------------------------------------
# set_appearance
# --------------------------------------------------------------------------


class TestSetAppearance:
    @pytest.mark.asyncio
    async def test_requires_active_model(self) -> None:
        adapter = _IOHarness(current_model=None)
        result = await adapter.set_appearance(1.0, 0.0, 0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active model"

    @pytest.mark.asyncio
    async def test_rejects_negative_channel(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace())
        result = await adapter.set_appearance(-1.0, 0.0, 0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "must be >= 0" in result.error

    @pytest.mark.asyncio
    async def test_rejects_transparency_out_of_range(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace())
        result = await adapter.set_appearance(0.5, 0.5, 0.5, transparency=1.5)
        assert result.status == AdapterResultStatus.ERROR
        assert "0 and 1" in result.error

    @pytest.mark.asyncio
    async def test_rejects_channel_above_255(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace())
        result = await adapter.set_appearance(300.0, 0.0, 0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "0-1 or 0-255" in result.error

    @pytest.mark.asyncio
    async def test_success_normalizes_0_255_range_and_confirms(self) -> None:
        calls = {"get": 0, "set_values": None}

        def get_values(option, config):
            calls["get"] += 1
            if calls["get"] == 1:
                return [0.5, 0.5, 0.5, 1.0, 1.0, 0.3, 0.3, 0.0, 0.0]
            return [1.0, 0.0, 0.0, 1.0, 1.0, 0.3, 0.3, 0.5, 0.0]

        def set_values(values, option, config):
            calls["set_values"] = values
            return True

        model = SimpleNamespace(
            Extension=SimpleNamespace(
                GetMaterialPropertyValues=get_values,
                SetMaterialPropertyValues=set_values,
            ),
            GraphicsRedraw2=lambda: None,
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_appearance(255, 0, 0, transparency=0.5)

        assert result.is_success
        assert result.data["color"] == {"r": 1.0, "g": 0.0, "b": 0.0}
        assert result.data["color_255"] == [255, 0, 0]
        assert result.data["transparency"] == 0.5
        # The setter must have been reached with the nine values. On Windows
        # _variant_doubles wraps them in a VARIANT SAFEARRAY; without pywin32
        # (Linux CI) it hands back the plain list, so accept either shape.
        assert calls["set_values"] is not None
        passed = calls["set_values"]
        assert list(getattr(passed, "value", passed)) == pytest.approx(
            [1.0, 0.0, 0.0, 1.0, 1.0, 0.3, 0.3, 0.5, 0.0]
        )

    @pytest.mark.asyncio
    async def test_uses_default_base_values_when_current_is_unreadable(self) -> None:
        calls = {"n": 0}

        def get_values(option, config):
            calls["n"] += 1
            if calls["n"] == 1:
                return "not-a-list"
            return [0.25, 0.5, 0.75, 1.0, 1.0, 0.3, 0.3, 0.2, 0.0]

        model = SimpleNamespace(
            Extension=SimpleNamespace(
                GetMaterialPropertyValues=get_values,
                SetMaterialPropertyValues=lambda *a: True,
            ),
            GraphicsRedraw2=lambda: None,
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_appearance(0.25, 0.5, 0.75, transparency=0.2)
        assert result.is_success

    @pytest.mark.asyncio
    async def test_raises_when_colour_cannot_be_read_back(self) -> None:
        model = SimpleNamespace(
            Extension=SimpleNamespace(
                GetMaterialPropertyValues=lambda option, config: None,
                SetMaterialPropertyValues=lambda *a: True,
            ),
            GraphicsRedraw2=lambda: None,
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_appearance(0.2, 0.4, 1.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "could not be read back" in result.error

    @pytest.mark.asyncio
    async def test_raises_when_colour_did_not_take(self) -> None:
        model = SimpleNamespace(
            Extension=SimpleNamespace(
                GetMaterialPropertyValues=(
                    lambda option, config: [0.9, 0.9, 0.9, 1, 1, 0.3, 0.3, 0.0, 0.0]
                ),
                SetMaterialPropertyValues=lambda *a: True,
            ),
            GraphicsRedraw2=lambda: None,
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.set_appearance(0.0, 0.0, 0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "Colour did not take" in result.error


# --------------------------------------------------------------------------
# get_material_properties
# --------------------------------------------------------------------------


class TestGetMaterialProperties:
    @pytest.mark.asyncio
    async def test_requires_active_model(self) -> None:
        adapter = _IOHarness(current_model=None)
        result = await adapter.get_material_properties()
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active model"

    @pytest.mark.asyncio
    async def test_reports_assigned_material_and_derived_density(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = "solidworks materials.sldmat"
            return "6061 Alloy"

        model = SimpleNamespace(
            GetActiveConfiguration=lambda: SimpleNamespace(Name="Default"),
            GetMaterialPropertyName2=get_material_name,
            GetMassProperties=lambda: [0.0, 0.0, 0.0, 0.001, 0.05, 2.7],
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.get_material_properties()

        assert result.is_success
        assert result.data["assigned"] is True
        assert result.data["name"] == "6061 Alloy"
        assert result.data["database"] == "solidworks materials.sldmat"
        assert result.data["configuration"] == "Default"
        assert result.data["density"]["value"] == pytest.approx(2700.0)
        assert result.data["density"]["units"] == "kg/m^3"
        assert "not available" in result.data["notes"]

    @pytest.mark.asyncio
    async def test_reports_unassigned_when_material_name_is_blank(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = ""
            return ""

        model = SimpleNamespace(
            GetActiveConfiguration=lambda: SimpleNamespace(Name="Default"),
            GetMaterialPropertyName2=get_material_name,
            GetMassProperties=lambda: [0, 0, 0, 0, 0, 0],
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.get_material_properties()

        assert result.is_success
        assert result.data["assigned"] is False
        assert result.data["name"] is None
        # Zero volume must not be reported as a (bogus) infinite density.
        assert result.data["density"] is None

    @pytest.mark.asyncio
    async def test_density_none_when_mass_properties_unavailable(self) -> None:
        def get_material_name(config_name, holder):
            holder.value = "lib.sldmat"
            return "Steel"

        model = SimpleNamespace(
            GetActiveConfiguration=lambda: SimpleNamespace(Name="Default"),
            GetMaterialPropertyName2=get_material_name,
            GetMassProperties=123,  # neither callable nor a usable sequence
        )
        adapter = _IOHarness(current_model=model)
        result = await adapter.get_material_properties()

        assert result.is_success
        assert result.data["density"] is None


# --------------------------------------------------------------------------
# Helpers: _byref_int / _byref_bstr / _variant_doubles / _doc_type /
# _read_material_name / _bounding_box_tuple
# --------------------------------------------------------------------------


class TestByrefHelpers:
    def test_byref_int_returns_variant_seeded_at_zero(self) -> None:
        result = _byref_int()
        assert getattr(result, "value", None) == 0

    def test_byref_int_without_pywin32_returns_bare_zero(self) -> None:
        with patch.object(_io_module, "win32com", SimpleNamespace(client=SimpleNamespace())):
            assert _byref_int() == 0

    def test_byref_bstr_returns_variant_seeded_empty(self) -> None:
        result = _byref_bstr()
        assert getattr(result, "value", None) == ""

    def test_byref_bstr_without_pywin32_returns_bare_string(self) -> None:
        with patch.object(_io_module, "win32com", SimpleNamespace(client=SimpleNamespace())):
            assert _byref_bstr() == ""

    def test_variant_doubles_wraps_floats_in_a_safearray(self) -> None:
        result = _variant_doubles([1, 2.5, 3])
        # VARIANT-wrapped where pywin32 exists, a plain list where it does not.
        assert list(getattr(result, "value", result)) == [1.0, 2.5, 3.0]

    def test_variant_doubles_without_pywin32_returns_plain_list(self) -> None:
        with patch.object(_io_module, "win32com", SimpleNamespace(client=SimpleNamespace())):
            result = _variant_doubles([1.0, 2.0])
        assert result == [1.0, 2.0]


class TestDocType:
    def test_reads_get_type_via_get_attr_or_call(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace(GetType=lambda: 2))
        assert _doc_type(adapter) == 2

    def test_returns_none_when_attribute_missing(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace())
        assert _doc_type(adapter) is None

    def test_returns_none_for_non_numeric_value(self) -> None:
        adapter = _IOHarness(current_model=SimpleNamespace(GetType=lambda: "oops"))
        assert _doc_type(adapter) is None


class TestReadMaterialName:
    def test_normalizes_tuple_result_and_reads_byref_database(self) -> None:
        def get_name(config_name, holder):
            holder.value = "Lib.sldmat"
            return ("Steel",)

        model = SimpleNamespace(GetMaterialPropertyName2=get_name)
        adapter = _IOHarness(current_model=model)
        name, database = _read_material_name(adapter, model, "Default")
        assert name == "Steel"
        assert database == "Lib.sldmat"

    def test_handles_empty_tuple_result(self) -> None:
        def get_name(config_name, holder):
            holder.value = ""
            return ()

        model = SimpleNamespace(GetMaterialPropertyName2=get_name)
        adapter = _IOHarness(current_model=model)
        name, database = _read_material_name(adapter, model, "Default")
        assert name is None


class TestBoundingBoxTuple:
    def test_rounds_min_max_from_get_bounding_box_impl(self) -> None:
        fake_result = AdapterResult(
            status=AdapterResultStatus.SUCCESS,
            data={
                "min": {"x": 0.12345, "y": -1.0, "z": 0.0},
                "max": {"x": 10.6789, "y": 5.0, "z": 2.0},
            },
        )
        with patch(
            "solidworks_mcp.adapters.solidworks.features._get_bounding_box_impl",
            lambda adapter: fake_result,
        ):
            adapter = _IOHarness(current_model=SimpleNamespace())
            result = _bounding_box_tuple(adapter)
        assert result == (0.123, -1.0, 0.0, 10.679, 5.0, 2.0)

    def test_returns_none_when_impl_reports_error(self) -> None:
        with patch(
            "solidworks_mcp.adapters.solidworks.features._get_bounding_box_impl",
            lambda adapter: AdapterResult(status=AdapterResultStatus.ERROR, error="x"),
        ):
            adapter = _IOHarness(current_model=SimpleNamespace())
            assert _bounding_box_tuple(adapter) is None

    def test_returns_none_when_min_max_keys_are_missing(self) -> None:
        fake_result = AdapterResult(
            status=AdapterResultStatus.SUCCESS, data={"min": {}, "max": {}}
        )
        with patch(
            "solidworks_mcp.adapters.solidworks.features._get_bounding_box_impl",
            lambda adapter: fake_result,
        ):
            adapter = _IOHarness(current_model=SimpleNamespace())
            assert _bounding_box_tuple(adapter) is None
