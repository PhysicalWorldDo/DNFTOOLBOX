# 物理世界的工具箱

用于集中安装、更新、启动和管理 DNF 工具的 Windows 桌面工具箱。

## 当前规则

- 工具箱本体代码放在本仓库。
- 工具箱本体 release 包只发布一个可运行 exe 的 zip。
- 工具列表、工具 manifest、工具包地址放在 `DNFTOOLBOX-Registry`。
- 每个工具的安装包放在各自工具仓库的 GitHub Releases。
- `docs/`、`scripts/`、`tests/` 只保留在本地，不推送到 GitHub。

## 运行

开发环境：

```powershell
python -m pip install -r requirements.txt
python toolbox.py
```

Release 用户只需要下载并运行 zip 内的 exe。首次运行会在 exe 同级目录生成：

```text
config/
tools/
downloads/
cache/
logs/
```

## 发布工具箱本体

1. 更新代码并确认版本号：

```text
physical_toolbox/__init__.py
```

2. 打包单文件 exe：

```powershell
pyinstaller --noconfirm --clean --onefile --windowed `
  --name PhysicalWorldToolbox `
  --icon physical_toolbox/assets/toolbox-icon.ico `
  --add-data "physical_toolbox/assets/toolbox-icon.ico;physical_toolbox/assets" `
  toolbox.py
```

3. 生成 release zip，zip 内只保留：

```text
PhysicalWorldToolbox.exe
```

4. 上传到本仓库 GitHub Releases，例如：

```powershell
gh release create v0.1.0 artifacts/release/PhysicalWorldToolbox-0.1.0-win-x64.zip `
  --repo PhysicalWorldDo/DNFTOOLBOX `
  --title "物理世界的工具箱 v0.1.0"
```

5. 计算 zip 的 SHA256，并在 `DNFTOOLBOX-Registry/index.json` 的 `toolbox` 节点写入：

```json
{
  "latestVersion": "0.1.0",
  "minSupportedVersion": "0.1.0",
  "releaseUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/tag/v0.1.0",
  "packageUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/download/v0.1.0/PhysicalWorldToolbox-0.1.0-win-x64.zip",
  "sha256": "填写 release zip 的 sha256",
  "changelog": []
}
```

## 工具箱本体更新

工具箱启动后会异步检查 `DNFTOOLBOX-Registry/index.json`。

发现本体新版本后，用户可以在右上角菜单下载新版。下载完成并校验 SHA256 后，工具箱会启动独立 updater，退出当前进程，再覆盖程序文件并重启新版工具箱。

更新时保留：

```text
config/
tools/
downloads/
cache/
logs/
```

## 工具项目地址

工具 manifest 支持 `projectUrl` 字段。工具箱内右键工具项可以复制项目地址。

优先级：

1. `projectUrl`
2. 工具 manifest 地址
3. 本地工具目录

## License

GPL-3.0。具体条款见 [LICENSE](LICENSE)。
