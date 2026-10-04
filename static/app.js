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

  // 神社は鳥居、寺院は三重塔で表す（国土地理院の外国人向け地図記号にならう）
  var ICONS = {
    shrine:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="currentColor">' +
      '<path d="M2 4.2 Q12 6.6 22 4.2 L22 6.6 Q12 8.6 2 6.6 Z"/>' + // 笠木（上の反った横木）
      '<rect x="4.5" y="10" width="15" height="1.8"/>' + // 貫（下の横木）
      '<rect x="6.2" y="7" width="2" height="14"/><rect x="15.8" y="7" width="2" height="14"/>' + // 柱
      '<rect x="11.1" y="7.6" width="1.8" height="2.6"/>' + // 額束
      "</g></svg>",
    temple:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="currentColor">' +
      '<rect x="11.3" y="0.8" width="1.4" height="4.6"/>' + // 相輪
      '<path d="M5 8.2 Q9.5 7.6 12 5 Q14.5 7.6 19 8.2 L18.4 9 H5.6 Z"/><rect x="9" y="9" width="6" height="2"/>' +
      '<path d="M3.5 13.2 Q9 12.6 12 10 Q15 12.6 20.5 13.2 L19.9 14 H4.1 Z"/><rect x="8.5" y="14" width="7" height="2"/>' +
      '<path d="M2 18.2 Q8.5 17.6 12 15 Q15.5 17.6 22 18.2 L21.4 19 H2.6 Z"/><rect x="8" y="19" width="8" height="3"/>' +
      '<rect x="6" y="22" width="12" height="1.4"/>' + // 基壇
      "</g></svg>",
  };

  function markerIcon(type) {
    var kind = ICONS[type] ? type : "other";
    return L.divIcon({
      className: "site-marker site-marker--" + kind,
      html: ICONS[type] || "",
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -15],
    });
  }

  var markers = points.map(function (p) {
    var marker = L.marker([p.lat, p.lng], { icon: markerIcon(p.type), title: p.name, riseOnHover: true });
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
