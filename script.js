document.addEventListener("DOMContentLoaded", () => {
  const daysEl = document.getElementById("days");
  const hoursEl = document.getElementById("hours");
  const minutesEl = document.getElementById("minutes");
  const secondsEl = document.getElementById("seconds");

  if (daysEl && hoursEl && minutesEl && secondsEl) {
    function pad(value) {
      return String(value).padStart(2, "0");
    }

    function getNextWeeklyReset() {
      const now = new Date();
      const reset = new Date(now);
      const daysUntilSunday = (7 - now.getDay()) % 7;

      reset.setDate(now.getDate() + daysUntilSunday);
      reset.setHours(23, 59, 59, 999);

      if (reset <= now) {
        reset.setDate(reset.getDate() + 7);
      }

      return reset.getTime();
    }

    function updateCountdown() {
      const targetTime = getNextWeeklyReset();
      const distance = targetTime - Date.now();

      if (distance <= 0) {
        daysEl.textContent = "00";
        hoursEl.textContent = "00";
        minutesEl.textContent = "00";
        secondsEl.textContent = "00";
        return;
      }

      const days = Math.floor(distance / (1000 * 60 * 60 * 24));
      const hours = Math.floor((distance / (1000 * 60 * 60)) % 24);
      const minutes = Math.floor((distance / (1000 * 60)) % 60);
      const seconds = Math.floor((distance / 1000) % 60);

      daysEl.textContent = pad(days);
      hoursEl.textContent = pad(hours);
      minutesEl.textContent = pad(minutes);
      secondsEl.textContent = pad(seconds);
    }

    updateCountdown();
    window.setInterval(updateCountdown, 1000);
  }

  const referralsBody = document.getElementById("referrals-body");

  if (!referralsBody) {
    return;
  }

  const statusMap = {
    0: "Active",
    1: "Inactive",
    2: "Stolen"
  };

  const podiumEls = {
    first: {
      avatar: document.getElementById("first-avatar"),
      name: document.getElementById("first-name"),
      score: document.getElementById("first-score"),
      status: document.getElementById("first-status")
    },
    second: {
      avatar: document.getElementById("second-avatar"),
      name: document.getElementById("second-name"),
      score: document.getElementById("second-score"),
      status: document.getElementById("second-status")
    },
    third: {
      avatar: document.getElementById("third-avatar"),
      name: document.getElementById("third-name"),
      score: document.getElementById("third-score"),
      status: document.getElementById("third-status")
    }
  };

  const referralTotalEl = document.getElementById("referral-total");
  const wageredTotalEl = document.getElementById("wagered-total");
  const activeRange = "7";

  function formatMoney(value) {
    return Number(value || 0).toFixed(2);
  }

  function renderEmptyPodiumEntry(slot, placeLabel) {
    const target = podiumEls[slot];

    if (!target) {
      return;
    }

    target.avatar.src = "mrfrog.png";
    target.avatar.alt = `${placeLabel} placeholder`;
    target.name.textContent = "Open Spot";
    target.score.textContent = "0.00";
    target.status.textContent = "Status: Waiting";
  }

  function renderPodiumEntry(slot, entry) {
    const target = podiumEls[slot];

    if (!target || !entry) {
      return;
    }

    target.avatar.src = entry.avatar;
    target.avatar.alt = `${entry.username} avatar`;
    target.name.textContent = entry.username;
    target.score.textContent = formatMoney(entry.wagered);
    target.status.textContent = `Status: ${statusMap[entry.status] || "Unknown"}`;
  }

  function renderTable(entries) {
    referralsBody.innerHTML = "";

    entries.forEach((entry) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="referrals-user-cell">
          <img class="referrals-user-avatar" src="${entry.avatar}" alt="${entry.username} avatar">
          <div>
            <div class="referrals-username">${entry.username}</div>
            <div class="referrals-steamid">${entry.steamid64}</div>
          </div>
        </td>
        <td>${formatMoney(entry.deposited)}</td>
        <td>${formatMoney(entry.wagered)}</td>
        <td><span class="status-pill status-pill--${(statusMap[entry.status] || "unknown").toLowerCase()}">${statusMap[entry.status] || "Unknown"}</span></td>
      `;
      referralsBody.appendChild(row);
    });
  }

  function applyPayload(payload) {
    const entries = Array.isArray(payload.data) ? [...payload.data] : [];

    if (entries.length === 0) {
      throw new Error("Leaderboard payload is empty");
    }

    entries.sort((a, b) => Number(b.wagered) - Number(a.wagered));

    if (entries[0]) {
      renderPodiumEntry("first", entries[0]);
    } else {
      renderEmptyPodiumEntry("first", "first");
    }

    if (entries[1]) {
      renderPodiumEntry("second", entries[1]);
    } else {
      renderEmptyPodiumEntry("second", "second");
    }

    if (entries[2]) {
      renderPodiumEntry("third", entries[2]);
    } else {
      renderEmptyPodiumEntry("third", "third");
    }

    referralTotalEl.textContent = String(entries.length);
    wageredTotalEl.textContent = formatMoney(
      entries.reduce((total, entry) => total + Number(entry.wagered || 0), 0)
    );

    renderTable(entries);
  }

  function loadFallbackData(range = activeRange) {
    let fallbackFile = "leaderboard_all_time.json";

    if (range === "7") {
      fallbackFile = "leaderboard_7_days.json";
    } else if (range === "30") {
      fallbackFile = "leaderboard_30_days.json";
    }

    return fetch(fallbackFile, { cache: "no-store" }).then((response) => {
      if (!response.ok) {
        throw new Error("Failed to load fallback leaderboard data");
      }
      return response.json();
    });
  }

  function loadLeaderboard(range = activeRange) {
    referralsBody.innerHTML = `
      <tr>
        <td colspan="4">Loading referral data...</td>
      </tr>
    `;

    const isLocalBackend =
      window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

    if (!isLocalBackend) {
      loadFallbackData(range)
        .then(applyPayload)
        .catch(() => {
          referralsBody.innerHTML = `
            <tr>
              <td colspan="4">Could not load referral data.</td>
            </tr>
          `;
        });
      return;
    }

    fetch(`/api/leaderboard?range=${encodeURIComponent(range)}`, { cache: "no-store" })
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
        return response.json().then((payload) => {
          if (payload && payload.fallback) {
            return payload.fallback;
          }
          throw new Error("Failed to load backend leaderboard data");
        });
      })
      .then(applyPayload)
      .catch(() => {
        loadFallbackData(range)
          .then(applyPayload)
          .catch(() => {
            referralsBody.innerHTML = `
              <tr>
                <td colspan="4">Could not load referral data.</td>
              </tr>
            `;
          });
      });
  }

  loadLeaderboard(activeRange);
});
