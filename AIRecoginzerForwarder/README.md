# AI 识别转发插件

> **版本：** 2.0.1  
> **作者：** liuyuexi1987  
> **功能：** MoviePilot 原生识别失败后转发给 AI Gateway，等待异步回调后二次整理

---

## 功能说明

这个插件用于在 MoviePilot 原生 TMDB 识别失败时，将标题和可用文件信息转发给 AI Gateway。

AI Gateway 在后台完成识别后，会回调本插件接口，然后由插件继续触发二次整理。

---

## 适用场景

- PT 资源原生识别失败补救
- 网盘拼音、漏词、规避版权命名识别
- 本地文件整理
- 115 / u115 云盘挂载回调后二次整理

---

## 部署关系

本插件只负责 MoviePilot 插件本体，不包含 AI 后端。

推荐搭配：

- `moviepilot-ai-recognizer-gateway`

DockerHub 镜像：

- `liuyuexi/moviepilot-ai-recognizer-gateway:2.0.0-alpha.1`
- 页面地址：[https://hub.docker.com/repository/docker/liuyuexi/moviepilot-ai-recognizer-gateway](https://hub.docker.com/repository/docker/liuyuexi/moviepilot-ai-recognizer-gateway)

同机 Docker 场景下，Webhook 地址一般填写：

```text
http://moviepilot-ai-recognizer-gateway:9000/webhook
```

---

## 识别增强模式

### standard

- 推荐默认使用
- 更适合 PT 规范命名
- 更稳，误匹配风险更低

### enhanced

- 更适合网盘拼音、漏词、规避版权命名
- 召回率更高，但误命中风险略高

---

## 安装说明

如果是通过 MoviePilot 本地安装 ZIP 包，请确保压缩包内包含：

- `AIRecoginzerForwarder/__init__.py`
- `AIRecoginzerForwarder/README.md`
- `AIRecoginzerForwarder/requirements.txt`

---

## 说明

- 建议保持 MoviePilot 原生识别优先
- 插件只在原生识别失败时兜底
- AI 最终 `tmdb_id` 以 Gateway 的 TMDB 复核结果为准
- Gateway 镜像当前同时支持 `linux/amd64` 与 `linux/arm64`
