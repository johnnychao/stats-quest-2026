# 執行環境

本發布版本已於 Windows、Anaconda CPython 3.13.9，依 `requirements.txt` 鎖定版本重建與測試。建議另建虛擬環境後執行：

```powershell
python -m pip install -r requirements.txt
```

Colab 或本機環境必須能匯入 `sklearn`（套件名稱為 `scikit-learn`）。Codex 或其他工具隨附的 bundled Python 若沒有 sklearn，只代表該工具執行環境未安裝課程依賴，**不代表 Notebook 或教材失敗**；請切換到上述已驗證環境或依鎖定檔安裝，不要把工具內建 Python 當成課程驗收環境。

公開 Notebook 與資料 URL 固定到 tag `v1.0.0`，返回入口固定為 `https://johnnychao.github.io/stats-quest-2026/`，瀏覽器進度鍵為 `statsquest2026:prod`。遠端 tag 尚未建立前，連結預期無法開啟。
