# שלום כהן – Personal Portfolio Resume (Elementor, InBio Light)

תבנית Elementor של אתר One Page אישי למפתח WordPress ו-PHP פרילנסר, עם אזורי SEO/GEO ו-PPC.
העיצוב מבוסס על InBio Light (רקע ‎#ECF0F3, צבע ראשי ‎#FF014F וכרטיסים בסגנון ניאומורפי).

יש שתי גרסאות של אותו עמוד:

| קובץ | דורש | ווידג'טים |
|---|---|---|
| `elementor/shalom-cohen-portfolio-inbio-pro.json` | **Elementor Pro** | Nav Menu + Sticky Header, Progress Tracker, Animated Headline, Blockquote, Flip Box (שירותים), Call to Action (תיק עבודות), Form (צור קשר), Share Buttons, Motion Effects ו-Custom CSS |
| `elementor/shalom-cohen-portfolio-inbio.json` | Elementor Free | Heading, Text Editor, Button, Image, Icon Box, Icon List, Social Icons, Counter, Progress Bar, Accordion, HTML, Shortcode ו-Spacer |

- **מחולל:** `tools/build_template.py`. אחרי עריכת התוכן מריצים `python3 tools/build_template.py` לגרסת Free ו-`python3 tools/build_template.py --pro` לגרסת Pro.
- **ווידג'טים:** בשתי הגרסאות רק ווידג'טים קלאסיים במבנה Section → Column, בלי ווידג'טים Atomic. גם בגרסת Pro יש ווידג'טים בסיסיים (Heading, Text, Counter, Progress, Accordion), כי ל-Pro אין ווידג'ט מקביל להם.
- **טיפוגרפיה:** בכל הווידג'טים הגופן הוא `Assistant` וכל גדלי הגופן בפיקסלים (כולל גדלים למובייל).

## ייבוא

1. בלוח הבקרה של וורדפרס: **תבניות → תבניות שמורות → ייבוא תבניות** ובוחרים את קובץ ה-JSON.
2. יוצרים עמוד חדש, פותחים אותו באלמנטור, לוחצים על אייקון התיקייה ובוחרים **התבניות שלי → הוסף**.
3. בהגדרות העמוד (⚙) קובעים פריסה **Elementor Canvas**, כי לתבנית יש כותרת עליונה ופוטר משלה.
4. מומלץ לקבוע ב-**הגדרות אתר → גופנים גלובליים** את הגופן `Assistant`. הגדרות שפת האתר צריכות להיות עברית (RTL).

## גרסת Pro – הגדרה חובה: תפריט

ווידג'ט Nav Menu מציג תפריט וורדפרס קיים. לפני הייבוא:
1. **מראה → תפריטים** → יוצרים תפריט חדש בשם **`one-page-menu`**.
2. מוסיפים **קישורים מותאמים** (Custom Links): `#home` בית · `#services` שירותים · `#marketing` SEO & PPC ·
   `#portfolio` תיק עבודות · `#resume` קורות חיים · `#faq` שאלות נפוצות · `#contact` צור קשר.
3. אם התפריט נקרא אחרת, בוחרים אותו בהגדרות הווידג'ט Nav Menu בכותרת העליונה.

טופס צור קשר (Pro Form) שולח מייל ל-`shalomco185@gmail.com`. מומלץ להתקין תוסף SMTP (למשל WP Mail SMTP) כדי שהמיילים לא ייפלו לספאם.
ה-CSS של העיצוב הניאומורפי נמצא ב-Custom CSS של סקשן הכותרת העליונה.

## מבנה העמוד (עוגנים)

`#home` פתיח · `#about` קצת עליי + מונים · `#services` 9 שירותים · `#marketing` SEO/GEO ו-PPC ·
`#process` תהליך עבודה · `#portfolio` 12 פרויקטים נבחרים + 26 נוספים · `#accessibility` 43+ פרויקטי נגישות ·
`#resume` ציר זמן של ניסיון והשכלה · `#skills` מדי כישורים · `#clients` חברות · `#faq` 13 שאלות ותשובות · `#contact` צור קשר.

## GEO / AEO

- בווידג'ט האקורדיון של השאלות הנפוצות מופעלת האפשרות **FAQ Schema**, כך שאלמנטור מייצר JSON-LD מסוג `FAQPage`.
- בווידג'ט ה-HTML שבכותרת יש JSON-LD מסוג `Person` ו-`ProfessionalService` (שם, תפקיד, אשדוד, השכלה, תחומי מומחיות). בגרסת Free נמצא באותו ווידג'ט גם ה-CSS של הצלליות.
- התשובות כתובות בגישת answer-first: המשפט הראשון עונה ישירות על השאלה ומזכיר ישויות (שם, מקום, טכנולוגיות).

## מה צריך להשלים אחרי הייבוא

- [ ] **תמונות:** בפתיח ובצור קשר יש תמונת placeholder. צריך להחליף אותן בתמונה שלכם.
- [ ] **צילומי מסך של הפרויקטים** נטענים כרגע משירות mshots של WordPress.com. מומלץ להעלות צילומי מסך לספריית המדיה (עדיף WebP) בשביל מהירות ו-SEO.
- [ ] **(גרסת Free בלבד) טופס יצירת קשר:** מתקינים Contact Form 7 ומחליפים את `REPLACE_ME` ב-shortcode במזהה הטופס. אם יש לכם Elementor Pro אפשר להחליף בווידג'ט Form. עד אז הכפתורים של וואטסאפ ומייל עובדים.
- [ ] **(גרסת Pro) צילומי מסך:** בכרטיסי Call to Action מחליפים את תמונת הרקע.
- [ ] **LinkedIn:** בשני ווידג'טי הרשתות החברתיות הקישור הוא `#`.
- [ ] **אחוזי הכישורים** הם הערכה ראשונית שכדאי לעדכן לפי שיקול דעתכם.
- [ ] כדאי להוסיף `url` ו-`sameAs` (פרופילים ברשתות) ל-JSON-LD אחרי שהדומיין מוכן.
