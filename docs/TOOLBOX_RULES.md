# 物理世界的工具箱规则

本文档固定“物理世界的工具箱”的第一版工具管理规则。当前采用“方案二起步，按方案三设计目录”：工具箱本体保持轻量，通过 GitHub 拉取远程清单和工具版本信息，安装包放在 GitHub Releases，本地工具按插件化目录管理。

## 目标

- 工具箱负责工具的展示、下载、安装、更新、卸载、启动。
- 每个工具独立打包、独立发布、独立更新。
- 工具程序和用户配置分离，更新时默认保留用户配置。
- 支持 stable 和 beta 频道。
- 支持查看并下载不同历史版本。
- 支持远程下架、禁用问题版本、提示更新公告。

## GitHub 仓库分工

建议至少使用两个仓库：

```text
PhysicalWorldToolbox/
  用途：工具箱主程序源码、构建脚本、发行版本

PhysicalWorldToolbox-Index/
  用途：远程工具清单、工具 manifest、公告、图标、版本记录
```

安装包不直接提交到 Git 仓库，统一放 GitHub Releases：

```text
PhysicalWorldToolbox-Packages Releases
  damage_calculator-v1.2.0
    damage_calculator-1.2.0-win-x64.zip
  equipment_compare-v1.0.0
    equipment_compare-1.0.0-win-x64.zip
```

## 远程更新仓库结构

```text
PhysicalWorldToolbox-Index/
  index.json
  announcements.json
  icons/
    damage_calculator.png
  tools/
    damage_calculator.json
    equipment_compare.json
```

工具箱启动或用户点击“检查更新”时，先读取 `index.json`。`index.json` 负责总入口、工具箱本体更新信息和工具 manifest 引用；具体工具版本包信息仍放在各工具 manifest 中。

```json
{
  "schemaVersion": 1,
  "toolbox": {
    "latestVersion": "1.0.0",
    "minSupportedVersion": "1.0.0",
    "releaseUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/tag/v1.0.0",
    "packageUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/download/v1.0.0/PhysicalWorldToolbox-1.0.0-win-x64.zip",
    "sha256": "填写工具箱安装包 sha256",
    "size": 52428800,
    "changelog": [
      "新增工具箱本体更新提示",
      "支持下载并校验新版工具箱安装包"
    ]
  },
  "tools": [
    {
      "id": "damage_calculator",
      "name": "伤害计算器",
      "category": "角色工具",
      "manifestUrl": "https://raw.githubusercontent.com/your-name/PhysicalWorldToolbox-Index/main/tools/damage_calculator.json"
    }
  ]
}
```

每个工具使用独立 manifest：

```json
{
  "schemaVersion": 1,
  "id": "damage_calculator",
  "name": "伤害计算器",
  "category": "角色工具",
  "description": "用于计算角色装备、词条、增益后的伤害。",
  "icon": "https://raw.githubusercontent.com/your-name/PhysicalWorldToolbox-Index/main/icons/damage_calculator.png",
  "entry": "bin/DamageCalculator.exe",
  "needAdmin": false,
  "latest": {
    "stable": "1.2.0",
    "beta": "1.3.0-beta.1"
  },
  "versions": [
    {
      "version": "1.2.0",
      "channel": "stable",
      "releaseDate": "2026-06-22",
      "packageUrl": "https://github.com/your-name/PhysicalWorldToolbox-Packages/releases/download/damage_calculator-v1.2.0/damage_calculator-1.2.0-win-x64.zip",
      "sha256": "填写安装包 sha256",
      "size": 15728640,
      "changelog": [
        "新增自定义词条计算",
        "修复部分装备加成错误"
      ],
      "minToolboxVersion": "1.0.0"
    }
  ],
  "permissions": ["network"],
  "tags": ["计算", "装备", "角色"],
  "status": "active",
  "blockedVersions": []
}
```

## 本地目录结构

```text
PhysicalWorldToolbox/
  toolbox.py
  config/
    app.json
    installed.json
  tools/
    damage_calculator/
      tool.json
      icon.png
      bin/
        DamageCalculator.exe
      config/
      data/
  cache/
    installing/
  downloads/
  logs/
```

## 工具目录规则

1. 每个工具必须有唯一 `id`。
2. 每个工具必须包含 `tool.json`。
3. 可执行程序和依赖文件放在 `bin/`。
4. 用户配置放在 `config/`。
5. 用户数据、缓存、运行产物放在 `data/`。
6. 工具入口由 `entry` 指定，工具箱不得写死具体 exe 名称。
7. 更新工具时默认替换 `bin/`、`tool.json`、`icon.png`。
8. 更新工具时不得覆盖 `config/` 和 `data/`。
9. 安装包必须校验 `sha256` 后才能解压安装。
10. 工具箱只管理生命周期，不把工具内部业务逻辑写进主程序。

## 版本规则

工具版本使用语义化版本：

```text
主版本.次版本.修复版本
1.2.3
```

测试版可以使用预发布标记：

```text
1.3.0-beta.1
```

频道规则：

- `stable`：默认频道，普通用户使用。
- `beta`：测试频道，用户主动切换后才提示。

`latest.stable` 和 `latest.beta` 分别声明各频道的最新版本。工具箱允许用户从 `versions` 中选择任意未封锁版本安装或回退。

## 安装流程

```text
用户点击未安装工具
→ 拉取工具 manifest
→ 用户选择版本
→ 下载 zip 到 downloads/
→ 校验 sha256
→ 解压到 cache/installing/
→ 检查 tool.json 和 entry 是否存在
→ 移动到 tools/工具id/
→ 写入 config/installed.json
→ 显示“已安装”
```

## 更新流程

```text
启动工具箱或点击检查更新
→ 拉取 index.json
→ 拉取每个已安装工具的 manifest
→ 对比本地版本和远程 latest stable/beta
→ 标记可更新
→ 用户点击更新
→ 下载新版
→ 校验 sha256
→ 备份旧版 bin/
→ 替换程序文件
→ 保留 config/ 和 data/
→ 更新 config/installed.json
```

## 工具箱本体更新流程

工具箱本体更新信息放在远程 `index.json` 的 `toolbox` 节点中，工具箱安装包放在 `DNFTOOLBOX` 仓库的 GitHub Releases。

```text
启动工具箱或点击检查更新
→ 后台拉取 index.json
→ 对比当前工具箱版本和 toolbox.latestVersion
→ 如有新版本，在顶部提示“发现工具箱新版本”
→ 用户点击右上角菜单
→ 可选择打开 Release 页面或下载工具箱更新
→ 下载 zip 到 downloads/
→ 校验 toolbox.sha256
→ 提示用户关闭当前工具箱后安装新版
```

工具箱启动时不得因为本体更新检查阻断 UI，也不得因为远程检查失败影响本地已安装工具的启动和使用。第一阶段不在运行中直接覆盖工具箱自身文件；后续如需自动替换，应使用独立 updater 进程在主程序退出后完成替换。

## 回退流程

```text
用户打开版本列表
→ 选择旧版本
→ 提示“这是降级操作”
→ 下载旧版
→ 校验 sha256
→ 备份当前版本
→ 替换程序文件
→ 保留 config/ 和 data/
→ 更新 config/installed.json
```

## 封锁版本规则

如果某个版本存在严重问题，可以在 manifest 中声明：

```json
{
  "blockedVersions": ["1.0.2"]
}
```

工具箱应当：

- 不允许新安装被封锁版本。
- 对已安装的被封锁版本显示明显提示。
- 引导用户更新到可用版本。

## 本地安装记录

`config/installed.json` 记录当前已安装工具：

```json
{
  "tools": {
    "damage_calculator": {
      "id": "damage_calculator",
      "name": "伤害计算器",
      "version": "1.2.0",
      "channel": "stable",
      "entry": "bin/DamageCalculator.exe",
      "installedAt": "2026-06-22T12:00:00+08:00",
      "updatedAt": "2026-06-22T12:00:00+08:00"
    }
  }
}
```

## 主程序第一版范围

第一版先完成：

- 读取远程或本地 `index.json`。
- 读取每个工具 manifest。
- 按分类展示工具。
- 显示工具详情和可选版本。
- 记录本地安装状态。
- 下载 zip。
- 校验 sha256。
- 解压安装。
- 启动已安装工具。
- 检查 stable/beta 更新。

第一版暂不强制完成：

- 用户评分。
- 在线账号。
- 工具评论。
- 差分更新。
- 多下载源测速。
- 工具沙箱隔离。
