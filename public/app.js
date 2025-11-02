const TARGET_SECTIONS = ["パフォーマンス指標", "基本行動", "組織の責任", "ガイダンスノート"];

const listContainer = document.getElementById("commitment-list");
const detailContainer = document.getElementById("commitment-detail");
const generatedInfo = document.getElementById("generated-info");

let currentButton = null;

async function loadData() {
  const response = await fetch("data/commitments.json");
  if (!response.ok) {
    throw new Error(`データの読み込みに失敗しました (status ${response.status})`);
  }
  return response.json();
}

function formatGeneratedAt(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return isoString;
  }
  return date.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });
}

function applyExternalLinkBehavior(root) {
  root.querySelectorAll('a[href^="http"]').forEach((link) => {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });
}

function htmlToPlain(html) {
  if (!html) return "";
  const temp = document.createElement("div");
  temp.innerHTML = html;
  return temp.textContent || temp.innerText || "";
}

function addTextBlock(doc, text, options) {
  if (!text) return;
  const { width, height } = doc.internal.pageSize;
  const margin = options.margin ?? 40;
  const indent = options.indent ?? 0;
  const lineHeight = options.lineHeight ?? 1.4;
  const fontSize = options.fontSize ?? 12;
  const fontStyle = options.fontStyle ?? "normal";
  const spacing = options.spacing ?? 6;
  let y = options.cursor.y;

  doc.setFont("helvetica", fontStyle);
  doc.setFontSize(fontSize);

  const usableWidth = width - margin * 2 - indent;
  const lines = doc.splitTextToSize(text, usableWidth);

  lines.forEach((line) => {
    if (y > height - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(line, margin + indent, y);
    y += fontSize * lineHeight;
  });

  y += spacing;
  options.cursor.y = y;
}

function downloadPdf(commitment) {
  if (!window.jspdf || !window.jspdf.jsPDF) {
    alert("PDF生成ライブラリが読み込まれていません。");
    return;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const cursor = { y: 40 };

  addTextBlock(doc, `2024のコミットメント番号${commitment.number}`, {
    fontSize: 18,
    fontStyle: "bold",
    spacing: 8,
    cursor,
  });
  addTextBlock(doc, `「${commitment.title}」`, {
    fontSize: 14,
    spacing: 10,
    cursor,
  });
  addTextBlock(doc, "要件", {
    fontSize: 14,
    fontStyle: "bold",
    spacing: 4,
    cursor,
  });
  commitment.requirements.forEach((req) => {
    addTextBlock(doc, `${req.id} ${req.text}`, {
      indent: 16,
      cursor,
    });
  });

  addTextBlock(doc, "2018に対応する", {
    fontSize: 14,
    fontStyle: "bold",
    spacing: 10,
    cursor,
  });

  commitment.legacy_commitments.forEach((legacy) => {
    addTextBlock(doc, `コミットメント番号${legacy.number}：「${legacy.title}」`, {
      fontSize: 13,
      fontStyle: "bold",
      spacing: 6,
      cursor,
    });

    const introPlain = htmlToPlain(legacy.intro_html || legacy.intro);
    addTextBlock(doc, introPlain, {
      indent: 12,
      cursor,
    });

    TARGET_SECTIONS.forEach((sectionName) => {
      const sectionHtml = legacy.sections_html?.[sectionName] || legacy.sections?.[sectionName];
      if (!sectionHtml) return;
      addTextBlock(doc, sectionName, {
        fontSize: 12,
        fontStyle: "bold",
        spacing: 4,
        cursor,
      });
      addTextBlock(doc, htmlToPlain(sectionHtml), {
        indent: 12,
        cursor,
      });
    });

    cursor.y += 4;
  });

  doc.save(`chs_commitment_${String(commitment.number).padStart(2, "0")}.pdf`);
}

function renderList(commitments) {
  const list = document.createElement("ul");
  commitments
    .slice()
    .sort((a, b) => a.number - b.number)
    .forEach((commitment) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${commitment.number}. ${commitment.title}`;
      button.addEventListener("click", () => {
        if (currentButton) {
          currentButton.classList.remove("active");
        }
        button.classList.add("active");
        currentButton = button;
        renderDetail(commitment);
      });
      item.append(button);
      list.append(item);
    });

  listContainer.innerHTML = "";
  listContainer.append(list);

  const firstButton = list.querySelector("button");
  if (firstButton) {
    firstButton.click();
  }
}

function renderDetail(commitment) {
  detailContainer.innerHTML = "";

  const heading = document.createElement("h2");
  heading.textContent = `2024のコミットメント番号${commitment.number}`;
  detailContainer.append(heading);

  const commitmentIcon = document.createElement("img");
  commitmentIcon.src = `images/commitments/${commitment.number}.png`;
  commitmentIcon.alt = `コミットメント${commitment.number}のアイコン`;
  commitmentIcon.className = "commitment-icon";
  detailContainer.append(commitmentIcon);

  const title = document.createElement("p");
  title.className = "commitment-title";
  title.textContent = `「${commitment.title}」`;
  detailContainer.append(title);

  const requirementsHeading = document.createElement("h3");
  requirementsHeading.textContent = "要件";
  detailContainer.append(requirementsHeading);

  const requirementList = document.createElement("ol");
  requirementList.className = "requirements";
  commitment.requirements.forEach((req) => {
    const li = document.createElement("li");
    const idSpan = document.createElement("span");
    idSpan.className = "requirement-id";
    idSpan.textContent = req.id;
    li.append(idSpan);
    li.append(document.createTextNode(` ${req.text}`));
    requirementList.append(li);
  });
  detailContainer.append(requirementList);

  const legacyHeading = document.createElement("h3");
  legacyHeading.textContent = "2018に対応する";
  detailContainer.append(legacyHeading);

  commitment.legacy_commitments.forEach((legacy) => {
    const legacySection = document.createElement("section");
    legacySection.className = "legacy";

    const legacyTitle = document.createElement("h4");
    legacyTitle.textContent = `コミットメント番号${legacy.number}：「${legacy.title}」`;
    legacySection.append(legacyTitle);

    const introHtml = legacy.intro_html || legacy.intro;
    if (introHtml) {
      const intro = document.createElement("div");
      intro.className = "legacy-intro";
      intro.innerHTML = introHtml;
      legacySection.append(intro);
    }

    TARGET_SECTIONS.forEach((sectionName) => {
      const contentHtml =
        legacy.sections_html?.[sectionName] || legacy.sections?.[sectionName];
      if (!contentHtml) return;
      const sectionHeading = document.createElement("h5");
      sectionHeading.textContent = sectionName;
      legacySection.append(sectionHeading);

      const sectionBody = document.createElement("div");
      sectionBody.className = "legacy-content";
      sectionBody.innerHTML = contentHtml;
      legacySection.append(sectionBody);
    });

    detailContainer.append(legacySection);
  });

  applyExternalLinkBehavior(detailContainer);

  const downloadBtn = document.createElement("button");
  downloadBtn.type = "button";
  downloadBtn.className = "download-pdf";
  downloadBtn.textContent = "PDFをダウンロード";
  downloadBtn.addEventListener("click", () => downloadPdf(commitment));
  detailContainer.append(downloadBtn);
}

function showError(message) {
  listContainer.innerHTML = `<p class="placeholder">${message}</p>`;
  detailContainer.innerHTML = "";
}

async function init() {
  try {
    const data = await loadData();
    if (data.generated_at) {
      generatedInfo.textContent = `最終更新: ${formatGeneratedAt(data.generated_at)}`;
    }
    renderList(data.commitments);
  } catch (error) {
    console.error(error);
    showError(error instanceof Error ? error.message : "不明なエラーが発生しました。");
  }
}

init();
