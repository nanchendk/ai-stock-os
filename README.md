# AI Stock OS V0.2

台股盤後研究平台（親友共享版原型）。資料來源：TWSE、TPEx 官方公開盤後資料。

- 每個台灣交易日 18:30 執行 GitHub Actions，更新 data/latest.json 和 data/history.json。
- 短線需 20 筆、波段需 60 筆歷史觀測；中長期暫不評分。
- 社群熱門榜尚未串接；不會顯示虛構數據。
- 本版沒有會員登入與持股功能；**不要將私人持股或個資提交到公開 Repository**。
- 研究排序不是投資建議，也不是預測上漲機率。

## 手動更新
Actions → AI Stock OS daily close → Run workflow。

## GitHub Pages
Settings → Pages → Build and deployment → Deploy from a branch → main / (root)。

## 資料品質
官方資料 schema、日期、盤後發布時間均須以 Actions 實際執行結果驗證。失敗時不可當作成功更新。
