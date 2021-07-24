import os

from keras.callbacks import (EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
                             TensorBoard)
from keras.optimizers import Adam

from nets.deeplab import Deeplabv3
from nets.deeplab_training import CE, Generator, LossHistory, dice_loss_with_CE
from utils.metrics import Iou_score, f_score

if __name__ == "__main__":     
    log_dir = "logs/"
    #------------------------------#
    #   输入图片的大小
    #------------------------------#
    input_shape = [512,512,3]
    #---------------------#
    #   分类个数+1
    #   特别注意
    #   2+1
    #---------------------#
    num_classes = 4
    #--------------------------------------------------------------------#
    #   建议选项：
    #   种类少（几类）时，设置为True
    #   种类多（十几类）时，如果batch_size比较大（10以上），那么设置为True
    #   种类多（十几类）时，如果batch_size比较小（10以下），那么设置为False
    #---------------------------------------------------------------------# 
    dice_loss = True
    #---------------------#
    #   主干网络选择
    #   mobilenet
    #   xception    
    #---------------------#
    backbone = "xception"
    #---------------------#
    #   下采样的倍数
    #   8和16
    #---------------------#
    downsample_factor = 16
    #------------------------------#
    #   数据集路径
    #------------------------------#
    dataset_path = "VOCdevkit/VOC2007/"

    # 获取model
    model = Deeplabv3(num_classes,input_shape,backbone=backbone,downsample_factor=downsample_factor)

    #-------------------------------------------#
    #   权值文件的下载请看README
    #   权值和主干特征提取网络一定要对应
    #-------------------------------------------#
    model_path = "model_data/deeplabv3_xception.h5"
    model.load_weights(model_path,by_name=True,skip_mismatch=True)

    # 打开数据集的txt
    with open(os.path.join(dataset_path, "ImageSets/Segmentation/train.txt"),"r") as f:
        train_lines = f.readlines()

    # 打开数据集的txt
    with open(os.path.join(dataset_path, "ImageSets/Segmentation/val.txt"),"r") as f:
        val_lines = f.readlines()
        
    #-------------------------------------------------------------------------------#
    #   训练参数的设置
    #   logging表示tensorboard的保存地址
    #   checkpoint用于设置权值保存的细节，period用于修改多少epoch保存一次
    #   reduce_lr用于设置学习率下降的方式
    #   early_stopping用于设定早停，val_loss多次不下降自动结束训练，表示模型基本收敛
    #-------------------------------------------------------------------------------#
    checkpoint_period = ModelCheckpoint(log_dir + 'ep{epoch:03d}-loss{loss:.3f}-val_loss{val_loss:.3f}.h5',
                                    monitor='val_loss', save_weights_only=True, save_best_only=False, period=1)
    reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1)
    early_stopping = EarlyStopping(monitor='val_loss', min_delta=0, patience=10, verbose=1)
    tensorboard = TensorBoard(log_dir=log_dir)
    loss_history = LossHistory(log_dir)

    if backbone=="mobilenet":
        freeze_layers = 146
    else:
        freeze_layers = 358

    for i in range(freeze_layers): model.layers[i].trainable = False
    print('Freeze the first {} layers of total {} layers.'.format(freeze_layers, len(model.layers)))

    #------------------------------------------------------#
    #   主干特征提取网络特征通用，冻结训练可以加快训练速度
    #   也可以在训练初期防止权值被破坏。
    #   Init_Epoch为起始世代
    #   Freeze_Epoch为冻结训练的世代
    #   Epoch总训练世代
    #   提示OOM或者显存不足请调小Batch_size
    #------------------------------------------------------#
    if True:
        lr              = 1e-4
        Init_Epoch      = 0
        Freeze_Epoch    = 50
        Batch_size      = 8
        
        # 交叉熵
        model.compile(loss = dice_loss_with_CE() if dice_loss else CE(),
                optimizer = Adam(lr=lr),
                metrics = [f_score()])

        gen             = Generator(Batch_size, train_lines, input_shape, num_classes, dataset_path).generate()
        gen_val         = Generator(Batch_size, val_lines, input_shape, num_classes, dataset_path).generate(False)

        epoch_size      = len(train_lines)//Batch_size
        epoch_size_val  = len(val_lines)//Batch_size

        if epoch_size == 0 or epoch_size_val == 0:
            raise ValueError("数据集过小，无法进行训练，请扩充数据集。")

        print('Train on {} samples, val on {} samples, with batch size {}.'.format(len(train_lines), len(val_lines), Batch_size))
        model.fit_generator(gen,
                steps_per_epoch=epoch_size,
                validation_data=gen_val,
                validation_steps=epoch_size_val,
                epochs=Freeze_Epoch,
                initial_epoch=Init_Epoch,
                callbacks=[checkpoint_period, reduce_lr, early_stopping, tensorboard, loss_history])
    
    for i in range(freeze_layers): model.layers[i].trainable = True

    if True:
        lr              = 1e-5
        Freeze_Epoch    = 50
        Unfreeze_Epoch  = 100
        Batch_size      = 4
        
        # 交叉熵
        model.compile(loss = dice_loss_with_CE() if dice_loss else CE(),
                optimizer = Adam(lr=lr),
                metrics = [f_score()])

        gen             = Generator(Batch_size, train_lines, input_shape, num_classes, dataset_path).generate()
        gen_val         = Generator(Batch_size, val_lines, input_shape, num_classes, dataset_path).generate(False)
        
        epoch_size      = len(train_lines)//Batch_size
        epoch_size_val  = len(val_lines)//Batch_size

        if epoch_size == 0 or epoch_size_val == 0:
            raise ValueError("数据集过小，无法进行训练，请扩充数据集。")

        print('Train on {} samples, val on {} samples, with batch size {}.'.format(len(train_lines), len(val_lines), Batch_size))
        model.fit_generator(gen,
                steps_per_epoch=epoch_size,
                validation_data=gen_val,
                validation_steps=epoch_size_val,
                epochs=Unfreeze_Epoch,
                initial_epoch=Freeze_Epoch,
                callbacks=[checkpoint_period, reduce_lr, early_stopping, tensorboard, loss_history])
