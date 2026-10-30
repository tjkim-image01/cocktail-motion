"""Observed 2026-10-09 Clip Creator upload + existing blog Clip link card.

The blog '내 클립' panel lists blog-created Clips, not this Creator upload.
attach_card therefore adds an actual registered Clip URL as an OG thumbnail
card; it does not claim to insert the native blog Clip player.

Use one live AsideMCP instance for the whole flow. Newly opened tabs close
when MCP exits. Account/profile setup is not automated. Upload only once;
after interruption inspect Creator contents before uploading again.
"""
import json
import time
from pathlib import Path
from .clip import AsideMCP


class NaverClipFlow:
    def __init__(self, client: AsideMCP):
        self.client = client

    def js(self, code):
        return self.client.repl(code)

    def snapshot(self):
        return self.js("console.log((await snapshot(page,{interactive:true})).tree);")

    def wait_for(self, text, attempts=40):
        for _ in range(attempts):
            state = self.snapshot()
            if text in state: return state
            time.sleep(1)
        raise RuntimeError(f'Expected UI state not seen: {text}; inspect before retrying')

    def file(self, selector, source):
        source=Path(source).resolve()
        if not source.is_file():raise FileNotFoundError(source)
        self.js("var clipDoc=await page._sendToTarget('DOM.getDocument',{depth:-1,pierce:true});"
            "var clipNode=await page._sendToTarget('DOM.querySelector',{nodeId:clipDoc.root.nodeId,selector:"
            +json.dumps(selector)+"});if(!clipNode.nodeId)throw new Error('FILE_INPUT_MISSING');"
            "await page._sendToTarget('DOM.setFileInputFiles',{nodeId:clipNode.nodeId,files:["
            +json.dumps(str(source))+"]});console.log((await snapshot(page,{interactive:true})).diff);")

    def upload(self, video, cover, description):
        """Register public Clip with AI label, returning discovered viewer URL.

        Caller must record the returned URL and reuse it instead of reuploading.
        Category here is specifically for this health-content workflow.
        """
        if len(description)>300:raise ValueError('Clip description exceeds 300 characters')
        self.js("await openTab('https://clipcreators.naver.com/web/dashboard');"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        state=self.wait_for('내 클립 바로가기')
        if '먼저 클립 프로필을 만들어주세요' in state:
            raise RuntimeError('Create the Clip profile before upload')
        self.js("await page.getByRole('button',{name:'업로드',exact:true}).first().click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.js("await page.getByRole('menuitem',{name:'동영상 업로드',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.wait_for('파일 선택')
        self.file('input[type=file]',video)
        self.wait_for('설명 *')
        self.js("await page.getByRole('textbox',{name:'설명 *',exact:true}).fill("
            +json.dumps(description,ensure_ascii=False)+");"
            "await page.getByRole('switch',{name:'AI 활용 설정',exact:true}).click();"
            "await page.getByRole('button',{name:'1차 카테고리',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.js("await page.getByRole('button',{name:'건강, 의학',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        self.js("await page.getByRole('button',{name:'2차 카테고리',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        self.js("await page.getByRole('button',{name:'생활건강',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        self.file('input[type=file][accept="image/jpeg,image/png"]',cover)
        for _ in range(90):
            if '인코딩 중' not in self.snapshot(): break
            time.sleep(1)
        else: raise RuntimeError('Encoding still running; inspect the saved draft')
        state=self.snapshot()
        if 'switch "AI 활용 설정"' not in state or '[checked]' not in state:
            raise RuntimeError('Inspect AI/public settings before registering')
        self.js("if(!(await page.getByRole('switch',{name:'AI 활용 설정',exact:true}).isChecked()))"
            "throw new Error('AI_LABEL_NOT_SET');"
            "if(!(await page.getByRole('switch',{name:'전체 공개',exact:true}).isChecked()))"
            "throw new Error('PUBLIC_NOT_SELECTED');"
            "await page.getByRole('button',{name:'등록',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.wait_for('등록 완료되었습니다.')
        state=self.snapshot()
        if '해피빈 기부콩' in state:
            self.js("await page.getByRole('button',{name:'닫기',exact:true}).click();"
                "console.log((await snapshot(page,{interactive:true})).tree);")
        self.wait_for('button "공개"')
        self.js("await page.getByRole('button',{name:'더보기',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        self.js("await page.getByRole('button',{name:'보러가기',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        for _ in range(10):
            out=self.js("console.log('VIEWERS:'+JSON.stringify(tabs.map(t=>t.url()).filter(u=>u.startsWith('https://clip.naver.com/contents?'))));")
            urls=json.loads(next(x[8:] for x in out.splitlines() if x.startswith('VIEWERS:')))
            if urls:return urls[-1]
            time.sleep(1)
        raise RuntimeError('Registered Clip viewer URL not captured; do not reupload')

    def attach_card(self, post_url, clip_url):
        """Add a Clip thumbnail card after the introduction; retain visibility.

        Explicit post URL avoids confusing old same-title drafts. Existing
        matching links cause a no-op. Existing paragraphs are verified before
        the final save. Returns the saved post URL.
        """
        if not post_url.startswith('https://blog.naver.com/') or not clip_url.startswith('https://clip.naver.com/contents?'):
            raise ValueError('Expected Naver post and registered Clip URLs')
        self.js('await openTab('+json.dumps(post_url)+');console.log((await snapshot(page,{interactive:true})).tree);')
        check=self.js("console.log('MATCH:'+await page.locator('a[href='+"
            +json.dumps(json.dumps(clip_url))+"+']').count());")
        if 'MATCH:0' not in check:return post_url
        self.js("await page.getByRole('link',{name:'수정',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.wait_for('banner:')
        self.js("var clipOriginal=await page.locator('.se-components-wrap > .se-component.se-text .se-text-paragraph').evaluateAll(es=>es.map(e=>e.innerText).filter(Boolean));"
            "await page.locator('.se-components-wrap > .se-component.se-text').nth(1).locator('.se-text-paragraph').last().click();"
            "await page.keyboard.press('End');await page.keyboard.press('Enter');")
        self.js("var clipInput=null;for(var clipFrame of page.frames().slice(1)){"
            "if(await clipFrame.evaluate(()=>!!document.body&&document.body.isContentEditable).catch(()=>false)){clipInput=clipFrame;break;}}"
            "if(!clipInput)throw new Error('NO_EDITOR_INPUT');"
            "await clipInput.evaluate(url=>{const dt=new DataTransfer();dt.setData('text/plain',url);"
            "document.body.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));},"
            +json.dumps(clip_url)+");await page.keyboard.press('Enter');"
            "console.log((await snapshot(page,{interactive:true})).diff);")
        self.wait_for('clip.naver.com')
        self.js("var clipBody=await page.locator('.se-components-wrap').innerText();"
            "if(!clipOriginal.every(t=>clipBody.includes(t)))throw new Error('ORIGINAL_TEXT_CHANGED');"
            "if(await page.locator('.se-components-wrap > .se-component.se-oglink').count()!==1)"
            "throw new Error('INSPECT_CARD_COUNT');"
            "await page.getByRole('button',{name:'발행',exact:true}).click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        state=self.wait_for('공개 설정')
        # Preserve the existing setting: do not select a different radio.
        self.js("await page.getByRole('button',{name:'발행',exact:true}).last().click();"
            "console.log((await snapshot(page,{interactive:true})).tree);")
        self.wait_for('isAfterUpdateOnly=true')
        out=self.js("console.log('SAVED:'+page.url());console.log('LINKS:'+JSON.stringify(await page.locator('a[href*=\"clip.naver.com\"]').evaluateAll(es=>es.map(e=>e.href))));")
        links=json.loads(next(x[6:] for x in out.splitlines() if x.startswith('LINKS:')))
        if clip_url not in links:raise RuntimeError('Saved post does not contain the Clip link')
        return next(x[6:] for x in out.splitlines() if x.startswith('SAVED:'))
