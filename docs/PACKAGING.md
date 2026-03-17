# 插件 ZIP 打包说明

## 目标

用于生成可在 MoviePilot 本地上传安装的插件 ZIP 包。

打包内容会保留以下标准结构：

```text
AIRecoginzerForwarder/
  __init__.py
  README.md
  requirements.txt
```

## 一键打包

在仓库根目录执行：

```bash
bash scripts/package-plugin.sh
```

## 输出位置

打包结果输出到：

```text
dist/
```

文件名格式：

```text
AIRecoginzerForwarder-<plugin_version>.zip
```

例如：

```text
AIRecoginzerForwarder-v2.0.0-alpha.1.zip
```

## 使用方式

1. 打开 MoviePilot
2. 进入 设置 -> 插件
3. 选择本地安装插件
4. 上传 `dist/` 下生成的 ZIP 文件

## 注意事项

- `plugin_version` 取自 `AIRecoginzerForwarder/__init__.py`
- 如果改了版本号，重新运行脚本即可生成对应文件名
- `dist/` 目录默认不纳入 Git 版本管理
