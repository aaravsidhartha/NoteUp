with open('frontend/app.js', 'r') as f:
    js = f.read()

# Fix 1: Move modal creation to happen on upload too, and fix export button encoding
old_upload_end = """        uploadStatus.textContent = '';
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
          item.cards.forEach(function(card) {
            addCardToPanel(card);
          });
        });
      } catch (err) {
        uploadStatus.textContent = 'Error uploading PDF. Please try again.';
        console.error(err);
      }
    });"""

new_upload_end = """        uploadStatus.textContent = '';
        ensureModalAndExport();
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
          item.cards.forEach(function(card) {
            addCardToPanel(card);
          });
        });
      } catch (err) {
        uploadStatus.textContent = 'Error uploading PDF. Please try again.';
        console.error(err);
      }
    });"""

old_library_end = """        uploadStatus.textContent = '';
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
          item.cards.forEach(function(card) {
            addCardToPanel(card);
          });
        });
      } catch (err) {
        uploadStatus.textContent = 'Error loading PDF.';
        console.error(err);
      }
    }"""

new_library_end = """        uploadStatus.textContent = '';
        ensureModalAndExport();
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
          item.cards.forEach(function(card) {
            addCardToPanel(card);
          });
        });
      } catch (err) {
        uploadStatus.textContent = 'Error loading PDF.';
        console.error(err);
      }
    }"""

new_function = """
function ensureModalAndExport() {
  if (!document.getElementById('export-btn')) {
    var toolbar = document.querySelector('.pdf-toolbar');
    var btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display:flex;gap:6px;margin-left:auto;';
    btnGroup.innerHTML = '<button id="export-btn" onclick="exportNotes()" style="padding:6px 14px;background:#6c63ff;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Export Notes</button>';
    toolbar.appendChild(btnGroup);
  }
  if (!document.getElementById('feature-modal')) {
    var modal = document.createElement('div');
    modal.id = 'feature-modal';
    modal.className = 'hidden';
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = '<div style="background:#1a1a2e;border-radius:12px;padding:32px;max-width:700px;width:90%;max-height:80vh;overflow-y:auto;position:relative;"><button onclick="document.getElementById(\'feature-modal\').classList.add(\'hidden\')" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#fff;font-size:20px;cursor:pointer;">✕</button><h2 id="modal-title" style="margin:0 0 16px;color:#fff;"></h2><div id="modal-body" style="color:#ccc;line-height:1.6;"></div></div>';
    document.body.appendChild(modal);
  }
}
"""

# Remove old inline export/modal creation from openPdfFromLibrary
old_inline = """      // Add toolbar buttons if not already there
        if (!document.getElementById('export-btn')) {
          var toolbar = document.querySelector('.pdf-toolbar');
          var btnGroup = document.createElement('div');
          btnGroup.style.cssText = 'display:flex;gap:6px;margin-left:auto;';
          btnGroup.innerHTML = '\u2b06 Export';
          toolbar.appendChild(btnGroup);
          // Add modal
          if (!document.getElementById('feature-modal')) {
            var modal = document.createElement('div');
            modal.id = 'feature-modal';
            modal.className = 'hidden';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
            modal.innerHTML = '\n\n\u2715\n\n';
            document.body.appendChild(modal);
          }
        }"""

if old_inline in js:
    js = js.replace(old_inline, '      // ensureModalAndExport() called after sections load')
    print("removed old inline modal/export")
else:
    print("inline block not found exactly - will add function anyway")

# Add the new function before renderAllPages
js = js.replace('async function renderAllPages()', new_function + '\nasync function renderAllPages()')

if old_upload_end in js:
    js = js.replace(old_upload_end, new_upload_end)
    print("upload handler patched")
else:
    print("WARNING: upload end not matched")

if old_library_end in js:
    js = js.replace(old_library_end, new_library_end)
    print("library handler patched")
else:
    print("WARNING: library end not matched")

with open('frontend/app.js', 'w') as f:
    f.write(js)
print("Done!")
