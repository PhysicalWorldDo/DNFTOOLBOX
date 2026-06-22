# 物理世界的工具箱

一个用于集中管理 DNF 工具的桌面工具箱框架。

当前第一版采用：

- GitHub 远程 `index.json` 管工具总列表。
- 单工具 manifest 管版本、频道、安装包地址和校验值。
- GitHub Releases 存放 zip 安装包。
- 本地 `tools/工具id/` 按插件化目录管理。

规则文档见 [docs/TOOLBOX_RULES.md](docs/TOOLBOX_RULES.md)。

## 启动

```powershell
python toolbox.py
```

UI 使用 PySide6。如果当前环境没有安装：

```powershell
python -m pip install PySide6
```

## 测试

```powershell
python -m pytest
```

## License

GPL-3.0。具体条款见 [LICENSE](LICENSE)。

## 目录

```text
physical_toolbox/
  app_config.py
  install_state.py
  manifest.py
  package_manager.py
  repository.py
  tool_grid.py
  ui.py
docs/
  TOOLBOX_RULES.md
examples/
  remote-index/
tests/
toolbox.py
```
