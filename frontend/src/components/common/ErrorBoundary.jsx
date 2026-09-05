import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught an error", error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback({ error: this.state.error, reset: this.handleReset });
    }

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
        <div className="card max-w-md w-full text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-danger-100 dark:bg-danger-900/30">
            <span className="text-danger-600 dark:text-danger-400 text-2xl">!</span>
          </div>
          <h2 className="text-lg font-semibold mb-2">문제가 발생했습니다</h2>
          {import.meta.env.DEV && this.state.error && (
            <pre className="text-left text-xs bg-gray-100 dark:bg-gray-900 rounded p-2 mb-4 overflow-auto max-h-40">
              {String(this.state.error?.stack || this.state.error)}
            </pre>
          )}
          <div className="flex gap-2 justify-center">
            <button className="btn-primary" onClick={this.handleReset}>
              다시 시도
            </button>
            <button className="btn" onClick={() => (window.location.href = "/")}>
              홈으로
            </button>
          </div>
        </div>
      </div>
    );
  }
}
