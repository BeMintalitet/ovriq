"""[QA] Navigation: alle app-sider har nav-bjaelke med vej ud til ovriq.xyz."""
import httpx
import pytest


@pytest.fixture()
def app(tmp_path):
    import importlib
    import ovriq.api.server as srv
    importlib.reload(srv)
    srv.boot(str(tmp_path / "j.jsonl"))
    return srv.app


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/dashboard", "/portal", "/credits/return",
                                  "/credits/cancel", "/vilkaar", "/privatliv"])
async def test_every_page_has_nav_and_home_link(app, path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://t") as http:
        t = (await http.get(path)).text
        assert 'class="ovnav"' in t, f"{path} mangler nav"
        assert "https://ovriq.xyz" in t, f"{path} mangler ovriq.xyz-link"
        assert "/dashboard" in t and "/portal" in t, f"{path} mangler krydslinks"


@pytest.mark.asyncio
async def test_dashboard_marks_active(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://t") as http:
        assert '<a href="/dashboard" class="active">' in (await http.get("/dashboard")).text
        assert '<a href="/portal" class="active">' in (await http.get("/portal")).text
