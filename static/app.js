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

  // 国土地理院の地図記号にならい、神社は鳥居、寺院は卍で表す
  var ICONS = {
    shrine:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="currentColor">' +
      '<path d="M2 4.2 Q12 6.6 22 4.2 L22 6.6 Q12 8.6 2 6.6 Z"/>' + // 笠木（上の反った横木）
      '<rect x="4.5" y="10" width="15" height="1.8"/>' + // 貫（下の横木）
      '<rect x="6.2" y="7" width="2" height="14"/><rect x="15.8" y="7" width="2" height="14"/>' + // 柱
      '<rect x="11.1" y="7.6" width="1.8" height="2.6"/>' + // 額束
      "</g></svg>",
    temple:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" ' +
      'stroke-linecap="square" d="M12 5V19M5 12H19M12 5H5M19 12V5M12 19H19M5 12V19"/></svg>',
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
