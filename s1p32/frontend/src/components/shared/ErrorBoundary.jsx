import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    // the fallback below is the only handling needed
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="card state-box" role="alert">
          <p>{this.props.label ? this.props.label + ' could not be shown.' : 'This part of the page could not be shown.'}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
