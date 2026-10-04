// 地図の表示
// - マウス操作: マーカーにカーソルを当てると写真付きのプレビュー。マーカーかプレビューをクリックで個別ページへ
// - タッチ操作: ホバーがないので、1 回目のタップでプレビュー、プレビューをタップで個別ページへ
(function () {
  var mapEl = document.getElementById("map");
  var dataEl = document.getElementById("map-points");
  if (!mapEl || !dataEl || !window.L) return;

  var points = JSON.parse(dataEl.textContent);
  var canHover = window.matchMedia("(hover: hover)").matches;
  var map = L.map(mapEl);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  // 写真・名称・分類をまとめたプレビュー要素を作る（innerHTML を使わず、文字列のエスケープ漏れを防ぐ）
  function preview(p) {
    var root = document.createElement("a");
    root.className = "preview";
    root.href = p.url;
    if (p.image) {
      var img = document.createElement("img");
      img.src = p.image;
      img.alt = "";
      root.appendChild(img);
    }
    var name = document.createElement("strong");
    name.textContent = p.name;
    root.appendChild(name);
    var meta = [p.type_label, p.last_visit].filter(Boolean).join(" · ");
    if (meta) {
      var span = document.createElement("span");
      span.textContent = meta;
      root.appendChild(span);
    }
    if (p.excerpt) {
      var text = document.createElement("p");
      text.textContent = p.excerpt;
      root.appendChild(text);
    }
    return root;
  }

  // ツールチップはカーソルがマーカーから離れると消えてクリックできないので、ポップアップをホバーで開閉する。
  // マーカーからプレビューへカーソルを移す間に閉じないよう、少し待ってから閉じる。
  function hoverPopup(marker, url) {
    var closeTimer = null;
    function open() {
      clearTimeout(closeTimer);
      if (!marker.isPopupOpen()) marker.openPopup();
    }
    function closeLater() {
      clearTimeout(closeTimer);
      closeTimer = setTimeout(function () { marker.closePopup(); }, 250);
    }
    marker.off("click"); // 既定の「クリックでポップアップ開閉」をやめ、個別ページへ移動する
    marker.on("click", function () { window.location.href = url; });
    marker.on("mouseover", open);
    marker.on("mouseout", closeLater);
    marker.on("popupopen", function (e) {
      var el = e.popup.getElement();
      el.addEventListener("mouseenter", open);
      el.addEventListener("mouseleave", closeLater);
    });
  }

  var colors = { temple: "#8a4b2a", shrine: "#c0392b" };
  var markers = points.map(function (p) {
    var marker = L.circleMarker([p.lat, p.lng], {
      radius: 8,
      color: colors[p.type] || "#555",
      weight: 2,
      fillOpacity: 0.85,
    });
    marker.bindPopup(preview(p), { className: "preview-popup", closeButton: !canHover, autoPan: !canHover });
    if (canHover) hoverPopup(marker, p.url);
    marker.point = p;
    return marker.addTo(map);
  });

  if (markers.length) {
    map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [40, 40], maxZoom: 15 });
  } else {
    map.setView([36.0, 137.0], 5); // 記録がないときは日本全体を表示
  }

  // タグで地図上のマーカーを絞り込む
  var buttons = document.querySelectorAll(".filters .tag");
  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      var tag = button.dataset.tag;
      buttons.forEach(function (b) { b.classList.toggle("is-active", b === button); });
      markers.forEach(function (m) {
        var show = tag === "" || m.point.tags.indexOf(tag) !== -1;
        if (show) m.addTo(map); else m.remove();
      });
    });
  });
})();
