export interface StatisticsRequestCoordinatorOptions<Params, Result> {
  debounceMs: number;
  request: (params: Params, signal: AbortSignal) => Promise<Result>;
  onLoading: (loading: boolean) => void;
  onSuccess: (result: Result) => void;
  onError: (error: unknown) => void;
}

export interface ScheduleOptions {
  immediate?: boolean;
}

/**
 * Coordinates debounced statistics requests and ignores stale completions.
 *
 * AbortController saves backend work when fetch honors cancellation.  The
 * monotonically increasing version is still required because a custom request
 * implementation may ignore its AbortSignal and resolve later.
 */
export function createStatisticsRequestCoordinator<Params, Result>(
  options: StatisticsRequestCoordinatorOptions<Params, Result>,
) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let activeController: AbortController | undefined;
  let latestVersion = 0;

  const schedule = (params: Params, scheduleOptions: ScheduleOptions = {}) => {
    const version = ++latestVersion;
    if (timer !== undefined) clearTimeout(timer);
    activeController?.abort();
    options.onLoading(true);

    const run = async () => {
      const controller = new AbortController();
      activeController = controller;
      try {
        const result = await options.request(params, controller.signal);
        if (version === latestVersion && !controller.signal.aborted) {
          options.onSuccess(result);
        }
      } catch (error: unknown) {
        if (version === latestVersion && !controller.signal.aborted) {
          options.onError(error);
        }
      } finally {
        if (version === latestVersion) {
          activeController = undefined;
          options.onLoading(false);
        }
      }
    };

    if (scheduleOptions.immediate) {
      void run();
    } else {
      timer = setTimeout(() => {
        timer = undefined;
        void run();
      }, options.debounceMs);
    }
  };

  const dispose = () => {
    latestVersion += 1;
    if (timer !== undefined) {
      clearTimeout(timer);
      timer = undefined;
    }
    activeController?.abort();
    activeController = undefined;
  };

  return { schedule, dispose };
}
