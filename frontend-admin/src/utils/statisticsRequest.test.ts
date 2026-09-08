import { afterEach, describe, expect, it, vi } from "vitest";
import { createStatisticsRequestCoordinator } from "./statisticsRequest";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("statistics request coordination", () => {
  it("debounces search changes before requesting statistics", async () => {
    vi.useFakeTimers();
    const request = vi.fn().mockResolvedValue("result");
    const coordinator = createStatisticsRequestCoordinator({
      debounceMs: 300,
      request,
      onLoading: vi.fn(),
      onSuccess: vi.fn(),
      onError: vi.fn(),
    });

    coordinator.schedule({ search: "f" });
    coordinator.schedule({ search: "fi" });
    coordinator.schedule({ search: "fire" });
    await vi.advanceTimersByTimeAsync(299);
    expect(request).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(request).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledWith(
      { search: "fire" },
      expect.any(AbortSignal)
    );
  });

  it("prevents an older response from replacing newer data or clearing loading", async () => {
    vi.useFakeTimers();
    const oldRequest = deferred<string>();
    const newRequest = deferred<string>();
    const request = vi
      .fn()
      .mockImplementationOnce(() => oldRequest.promise)
      .mockImplementationOnce(() => newRequest.promise);
    const onLoading = vi.fn();
    const onSuccess = vi.fn();
    const coordinator = createStatisticsRequestCoordinator({
      debounceMs: 300,
      request,
      onLoading,
      onSuccess,
      onError: vi.fn(),
    });

    coordinator.schedule({ search: "old" });
    await vi.advanceTimersByTimeAsync(300);
    coordinator.schedule({ search: "new" });
    await vi.advanceTimersByTimeAsync(300);

    oldRequest.resolve("old result");
    await Promise.resolve();
    await Promise.resolve();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onLoading).toHaveBeenLastCalledWith(true);

    newRequest.resolve("new result");
    await Promise.resolve();
    await Promise.resolve();
    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onSuccess).toHaveBeenCalledWith("new result");
    expect(onLoading).toHaveBeenLastCalledWith(false);
  });

  it("can schedule again after cleanup during React StrictMode effect replay", async () => {
    vi.useFakeTimers();
    const request = vi.fn().mockResolvedValue("result");
    const onSuccess = vi.fn();
    const coordinator = createStatisticsRequestCoordinator({
      debounceMs: 300,
      request,
      onLoading: vi.fn(),
      onSuccess,
      onError: vi.fn(),
    });

    coordinator.schedule({ search: "first mount" });
    coordinator.dispose();
    coordinator.schedule({ search: "strict replay" });
    await vi.advanceTimersByTimeAsync(300);
    await Promise.resolve();

    expect(request).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledWith(
      { search: "strict replay" },
      expect.any(AbortSignal)
    );
    expect(onSuccess).toHaveBeenCalledWith("result");
  });
});
