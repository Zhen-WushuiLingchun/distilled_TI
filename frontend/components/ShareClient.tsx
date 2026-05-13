"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { claimInvite, redeemInvite } from "@/lib/api";
import { getUserAccess, saveUserAccess } from "@/lib/runtime-store";

export function ShareClient() {
  const router = useRouter();
  const [invite, setInvite] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [hasLocalUser, setHasLocalUser] = useState(false);
  const [from, setFrom] = useState("");
  const [title, setTitle] = useState("Distilled TI 剧情测绘");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setInvite(params.get("invite") ?? "");
    setFrom(params.get("from") ?? "");
    setTitle(params.get("title") ?? "Distilled TI 剧情测绘");
    setHasLocalUser(Boolean(getUserAccess()));
  }, []);

  async function handleEnter() {
    if (!invite.trim()) {
      setStatus("这个分享链接没有邀请码，无法建立邀请关系。");
      return;
    }
    const existing = getUserAccess();
    if (existing) {
      try {
        setBusy(true);
        setStatus("正在把这条分享关系写入你的匿名关系网…");
        const profile = await claimInvite(existing, invite.trim());
        saveUserAccess({
          ...existing,
          handle: profile.handle,
          relationship_opt_in: profile.relationship_opt_in,
          recommendation_opt_in: profile.recommendation_opt_in,
        });
      } catch (reason) {
        setStatus(reason instanceof Error ? reason.message : "邀请关系写入失败。");
        setBusy(false);
        return;
      }
      router.push("/story");
      return;
    }
    if (!registerEmail.trim()) {
      setStatus("请输入注册邮箱；一个邮箱只能注册一个匿名档案。");
      return;
    }
    try {
      setBusy(true);
      setStatus("");
      const access = await redeemInvite(invite.trim(), registerEmail.trim());
      saveUserAccess(access);
      router.push("/story");
    } catch (reason) {
      setStatus(reason instanceof Error ? reason.message : "注册失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="share-shell">
      <section className="share-card fade-rise">
        <p className="label-mini">Shared Entry</p>
        <h1>{title}</h1>
        <p className="mt-4 max-w-2xl text-[color:var(--ink-muted)]">
          {from ? `${from} 邀请你进入同一个匿名关系网络。` : "有人分享了 Distilled TI 的剧情测绘入口。"}
          你会得到随机 handle；后台只记录邀请码关系和匿名画像，不需要真实姓名。
        </p>
        <div className="mt-6 rounded-[var(--r-lg)] bg-[color:var(--bg-sunken)] p-4">
          <p className="label-mini">Invite Code</p>
          <input className="field mt-2" value={invite} onChange={(event) => setInvite(event.target.value)} />
          {!hasLocalUser ? (
            <>
              <p className="label-mini mt-4">Register Email</p>
              <input
                className="field mt-2"
                type="email"
                value={registerEmail}
                onChange={(event) => setRegisterEmail(event.target.value)}
                placeholder="一个邮箱只能注册一个匿名档案"
              />
            </>
          ) : null}
          {status ? <p className="mt-2 text-xs text-[color:var(--danger-ink)]">{status}</p> : null}
        </div>
        <div className="mt-6 flex flex-wrap gap-2.5">
          <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void handleEnter()}>
            {busy ? "进入中…" : "使用邀请进入剧情模式"}
          </button>
          <button className="btn btn-ghost" type="button" onClick={() => router.push("/")}>
            先看首页
          </button>
        </div>
      </section>
    </main>
  );
}
