# הזרקת דרייברים אוטומטית וסטטוס ההסבה ל־Windows

הזרקה אמיתית מוסיפה חבילת INF/SYS/CAT למאגר הדרייברים של Windows.
העתקת SYS אל WIM דרך wimlib אינה עושה זאת. לאחר הזרקה ל־boot.wim,
Plug and Play בוחר דרייברים תואמים בזמן עליית WinPE. השינוי אינו מועבר
אוטומטית ל־Windows המותקן: גם install.wim או מערכת היעד זקוקים לשילוב נפרד.

## הכנת החבילה על המק

```bash
bash scripts/prepare-j413-driver-injection.command
```

הסקריפט אורז רק את חבילות ARM64 הבינריות השלמות שכבר נבנו, יחד עם
MANIFEST וסקריפטי Windows, בתיקייה פרטית חדשה. הוא מציג בנפרד אילו חבילות
כשירות להזרקה אוטומטית. אין העתקת WIM גדול, כתיבה למחיצות או שינוי באתחול.
כעת אין חבילת Apple מותאמת שמוכנה להזרקה אוטומטית. חבילת DockChannel
הבינרית קיימת, אך אתחול MTP/RTKit, DART, משאבים, פסיקות ופרסום HID אינם
שלמים. AGX גם אינו מוכן לחוזה החומרה של J413. אין סקריפט שיכול להשלים
את הקוד החסר באמצעות העתקת החבילות.

## שילוב אוטומטי באמצעות Windows ו־DISM

בדיקת התוכנית בלבד, ללא שינוי תמונה:

```powershell
.\inject-drivers.ps1 -Bundle . -BootWim 'C:\Media\sources\boot.wim' -PlanOnly
```

כאשר קיימות חבילות כשירות עם קטלוג שניתן לאמת, מריצים במסוף Windows
מוגבה. הפקודה הבאה משרתת עותק חדש של תמונת Setup באינדקס 2:

```powershell
.\inject-drivers.ps1 -Bundle . -BootWim 'C:\Media\sources\boot.wim' -OutputDirectory 'C:\J413-Serviced'
```

כדי לכלול גם את Windows שיותקן, מעבירים בנוסף `-InstallWim` ואת
`-InstallIndexes` של המהדורה הרצויה. אין ניחוש מהדורה. קובצי install.swm
מפוצלים אינם יעד לסקריפט הזה: נדרש install.wim לפני החלוקה, ומחלקים מחדש
רק אחרי השירות. כל תמונה שנבחרה חייבת להיות ARM64.

הסקריפט מאמת SHA-256, חומרה ו־PE32+ ARM64 native, דורש כשירות מפורשת
ברשומת החבילה ואימות קטלוג Windows, מעגן עותק פרטי ומפעיל DISM Add-Driver.
לאחר מכן הוא דורש שה־INF יופיע ברשימת הדרייברים של התמונה. רק אחרי שכל
האינדקסים הצליחו נוצרת תיקיית הפלט הסופית עם hashes ויומן DISM. בכישלון
מבוצע Discard לעיגון הפרטי; המקור נשאר ללא שינוי. אין ForceUnsigned,
שינוי BCD, התקנת מערכת או reboot. הזרקה ל־WIM אינה הוכחת פעולה בחומרה.

הסקריפט דורש Windows 10 ומעלה או WinPE לשירות בפועל. בדיקות PowerShell
מקומיות על macOS בדקו את פונקציית העבודה עם DISM מדומה; לא בוצע DISM
אמיתי על המק ולא נטען דרייבר חדש בזמן עליית Windows.

## מה ניתן לקחת מ־Aurora

הסקירה הנוכחית: `investigation/analysis/2026-11-06-driver-source-review.json`.
נבדק הקוד הנוכחי, לא רק שמות מאגרים. מאגר Windows-driver-samples שלהם
הוא fork של דוגמאות Microsoft; בעץ המלא שנבדק אין דרייבר Apple Silicon.

| חלק במימוש Linux | החוזה הדרוש ב־Windows | המצב אצלנו |
| --- | --- | --- |
| מיפוי בנקי config/data/IRQ מה־DTS | ACPI מדויק, משאבי PnP ממופים והפרדת בנקים | חסר; המשאב הראשון הנוכחי אינו FIFO data |
| IRQ domain עם mask/ack/demultiplex | ניתוב hypervisor/ACPI תקין ו־KMDF ISR/DPC שמזהה ומאשר מקור | חסר |
| RTKit helper ותחילת עבודת MTP | אתחול firmware, mailbox, power ו־recovery בבעלים מוסכמים | חסר |
| DMA/ring ו־DART | מיפוי DMA תואם לחומרה ול־Windows, כולל סדרי זיכרון | חסר |
| GPIO והעלאת קושחת Trackpad | בעלות power/reset ו־firmware תואם | חסר |
| גילוי ממשקים ותיאורי HID | התקני HID/VHF לפי descriptor אמיתי ותרגום דוחות מתאים | ליבת פענוח קיימת; מתאם מלא חסר |
| זיכרון מנוהל `devm_*` | זמן חיים לפי אירועי KMDF ושחרור לאחר סיום עבודה נדחית | תוקנה הקצאת מאגר מחדש ב־PrepareHardware; טרם נבדק בחומרה |
| DWC3/xHCI | קושחה וחוזה חיבור תקינים לפני Windows USBXHCI/USBHUB3/HIDUSB | קוד מובנה קיים ב־Windows; בעיית הקלט עוד לא אובחנה |
| DRM/Mesa | WDDM kernel/user drivers ו־Direct3D contracts | הסבת GPU מלאה אינה קיימת |

לכן הסבה נכונה אינה החלפת שמות פונקציות שורה־שורה. רצף הפרוטוקול יכול
להישמר, אך ניהול זיכרון, פסיקות, DMA, power, firmware ו־HID חייבים להתאים
ל־Windows. קוד Linux הרלוונטי שנבדק מציע MIT לצד GPL; כל העתקה עתידית
דורשת שמירת ההודעות והרישיון של הקובץ. תיקון זמן החיים וסקריפט DISM כאן
הם קוד Windows מקורי; לא הועתק אליהם מימוש Linux.

מקורות:
- https://github.com/aurora-silicon/linux/tree/0943983df73eb270720a7e6ba13b009ccfd14312/drivers/hid/dockchannel-hid
- https://github.com/aurora-silicon/Windows-driver-samples/tree/34c8e967f0fc9bac4febbad50e1999d0d8f5923f
- https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/add-and-remove-drivers-to-an-offline-windows-image
- https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/limitations-dollar-sign-winpedriver-dollar-sign
