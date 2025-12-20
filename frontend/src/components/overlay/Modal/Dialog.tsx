import React from 'react'
import { Modal, ModalProps } from './Modal'

/**
 * Dialog component - modal variant with actions and form dialogs
 */
export const Dialog: React.FC<ModalProps> = (props) => {
  return <Modal {...props} />
}

Dialog.displayName = 'Dialog'

