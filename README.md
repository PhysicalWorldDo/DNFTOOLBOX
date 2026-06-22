# 物理世界的工具箱

DNF 工具集中管理器，用于统一下载、安装、更新、卸载和启动工具。

## 下载

前往 [Releases](https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases) 下载最新版 zip，解压后运行：

```text
PhysicalWorldToolbox.exe
```

## 功能

- 按分类展示 DNF 工具
- 安装、卸载、启动工具
- 支持选择不同工具版本
- 后台检查工具和工具箱本体更新
- 下载进度与 SHA256 校验
- 工具箱本体可通过独立 updater 自动覆盖更新
- 右键工具可复制项目地址

## 开发运行

```powershell
python -m pip install -r requirements.txt
python toolbox.py
```

## 发布规则

- 本仓库只存放工具箱本体源码。
- Release zip 只包含 `PhysicalWorldToolbox.exe`。
- 工具列表和版本信息由 `DNFTOOLBOX-Registry` 管理。
- 发布新版工具箱后，同步更新 Registry 中的 `toolbox` 节点。

## License

GPL-3.0，详见 [LICENSE](LICENSE)。
